"""SQL Server collector.

Emits exactly the vendor-native metric names recording_rules/db_sqlserver.yml
already expects. "db" label names are preserved as-is (the recording rule
does the "database" rename itself). No "mode" label on mssql_lock_waits --
the recording rule doesn't consume one, so this module matches it literally.
"""
import pymssql
from prometheus_client.core import GaugeMetricFamily

from src.collectors.base import VendorAdapter
from src.collectors.query_stats import build_query_stats_families
from src.config import DatabaseTarget

# count/sum are exact (plain sums). max_elapsed_time is also exact -- SQL
# Server tracks the true per-statement maximum natively, not derived from
# the mean.
_QUERY_STATS_SQL = """
    SELECT SUM(execution_count) AS cnt, SUM(total_elapsed_time) AS total_time, MAX(max_elapsed_time) AS max_time
    FROM sys.dm_exec_query_stats
    WHERE execution_count > 0
"""

_CONNECTIONS_SQL = """
    SELECT DB_NAME(database_id) AS db, COUNT(*) AS cnt
    FROM sys.dm_exec_sessions
    WHERE database_id > 0 AND is_user_process = 1
    GROUP BY database_id
"""

_MAX_CONNECTIONS_SQL = "SELECT CAST(value_in_use AS INT) FROM sys.configurations WHERE name = 'user connections'"

# Worst-case (max) lag across all AG-protected databases on this instance --
# kept unlabeled to match the recording rule's literal expectation of a bare
# mssql_availability_group_log_send_queue_seconds metric.
_AG_LAG_SQL = """
    SELECT MAX(drs.log_send_queue_size / NULLIF(drs.log_send_rate, 0)) AS lag_seconds
    FROM sys.dm_hadr_database_replica_states drs
"""

_LOCK_WAITS_SQL = """
    SELECT DB_NAME(l.resource_database_id) AS db, COUNT(*) AS cnt
    FROM sys.dm_tran_locks l
    JOIN sys.dm_os_waiting_tasks wt ON l.lock_owner_address = wt.resource_address
    WHERE l.request_status = 'WAIT'
    GROUP BY l.resource_database_id
"""

_DEADLOCKS_SQL = """
    SELECT cntr_value
    FROM sys.dm_os_performance_counters
    WHERE counter_name = 'Number of Deadlocks/sec' AND instance_name = '_Total'
"""

_SIZE_SQL = """
    SELECT DB_NAME(database_id) AS db, SUM(CAST(size AS BIGINT) * 8 * 1024) AS bytes
    FROM sys.master_files
    GROUP BY database_id
"""

# sys.dm_exec_query_stats times are in microseconds.
_MICROSECONDS_PER_SECOND = 1e6


class SqlServerAdapter(VendorAdapter):
    def __init__(self, target: DatabaseTarget):
        super().__init__(target)

    def connect(self):
        conn = pymssql.connect(
            server=self.target.host,
            port=str(self.target.port),
            database=self.target.database,
            user=self.target.username,
            password=self.target.password,
            login_timeout=self.target.scrape_timeout_seconds,
            timeout=self.target.scrape_timeout_seconds,
            autocommit=True,  # read-only monitoring queries; no reason to hold a transaction open
        )
        return conn

    def is_alive(self, conn) -> bool:
        cur = conn.cursor()
        try:
            cur.execute("SELECT 1")
            cur.fetchone()
        finally:
            cur.close()
        return True

    def collect(self, conn) -> tuple[list, bool]:
        families: list = []
        had_error = False
        queries = [
            ("query_duration", lambda: self._query_duration_family(conn)),
            ("connections", lambda: self._connections_family(conn)),
            ("max_connections", lambda: self._max_connections_family(conn)),
            ("lock_waits", lambda: self._lock_waits_family(conn)),
            ("deadlocks", lambda: self._deadlocks_family(conn)),
            ("size", lambda: self._size_family(conn)),
            ("ag_lag", lambda: self._ag_lag_family(conn)),
        ]
        for label, builder in queries:
            result_families, err = self.safe_collect_family(label, builder)
            families.extend(result_families)
            had_error = had_error or err
        return families, had_error

    def _query_duration_family(self, conn):
        cur = conn.cursor()
        try:
            cur.execute(_QUERY_STATS_SQL)
            row = cur.fetchone()
        finally:
            cur.close()
        if not row or row[0] is None:
            return build_query_stats_families(
                "mssql_query_execution_seconds", "Query execution time from sys.dm_exec_query_stats", 0, 0.0, None
            )
        cnt, total_time, max_time = row
        return build_query_stats_families(
            "mssql_query_execution_seconds",
            "Query execution time from sys.dm_exec_query_stats",
            int(cnt),
            float(total_time) / _MICROSECONDS_PER_SECOND,
            float(max_time) / _MICROSECONDS_PER_SECOND,
        )

    def _connections_family(self, conn):
        cur = conn.cursor()
        try:
            cur.execute(_CONNECTIONS_SQL)
            rows = cur.fetchall()
        finally:
            cur.close()
        family = GaugeMetricFamily("mssql_connections", "Active user connections per database.", labels=["db"])
        for db, cnt in rows:
            family.add_metric([db], cnt)
        return family

    def _max_connections_family(self, conn):
        cur = conn.cursor()
        try:
            cur.execute(_MAX_CONNECTIONS_SQL)
            value = cur.fetchone()[0]
        finally:
            cur.close()
        family = GaugeMetricFamily("mssql_max_connections", "Configured max user connections (0 = unlimited).")
        family.add_metric([], value)
        return family

    def _ag_lag_family(self, conn):
        cur = conn.cursor()
        try:
            cur.execute(_AG_LAG_SQL)
            row = cur.fetchone()
        finally:
            cur.close()
        if not row or row[0] is None:
            return None
        family = GaugeMetricFamily(
            "mssql_availability_group_log_send_queue_seconds", "Worst-case AG log send queue lag in seconds."
        )
        family.add_metric([], float(row[0]))
        return family

    def _lock_waits_family(self, conn):
        cur = conn.cursor()
        try:
            cur.execute(_LOCK_WAITS_SQL)
            rows = cur.fetchall()
        finally:
            cur.close()
        family = GaugeMetricFamily("mssql_lock_waits", "Current lock waits per database.", labels=["db"])
        for db, cnt in rows:
            family.add_metric([db], cnt)
        return family

    def _deadlocks_family(self, conn):
        cur = conn.cursor()
        try:
            cur.execute(_DEADLOCKS_SQL)
            row = cur.fetchone()
        finally:
            cur.close()
        family = GaugeMetricFamily("mssql_deadlocks_per_second", "SQL Server's own Deadlocks/sec perf counter.")
        family.add_metric([], float(row[0]) if row else 0.0)
        return family

    def _size_family(self, conn):
        cur = conn.cursor()
        try:
            cur.execute(_SIZE_SQL)
            rows = cur.fetchall()
        finally:
            cur.close()
        family = GaugeMetricFamily("mssql_database_size_bytes", "Database size in bytes.", labels=["db"])
        for db, size_bytes in rows:
            family.add_metric([db], size_bytes)
        return family
