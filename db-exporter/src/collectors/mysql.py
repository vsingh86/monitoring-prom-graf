"""MySQL collector.

Emits exactly the vendor-native metric names recording_rules/db_mysql.yml
already expects. The connections/max-connections/row-lock/deadlock metrics
are genuinely global scalars in MySQL (no per-database breakdown), matching
the recording rule's own label_replace(..., "database", "mysql", ...) trick
-- so this module correctly emits them with no extra label at all.
"""
import mysql.connector
from prometheus_client.core import GaugeMetricFamily

from src.collectors.base import VendorAdapter
from src.collectors.query_stats import build_query_stats_families
from src.config import DatabaseTarget

# count/sum are exact (plain sums). MAX_TIMER_WAIT is also exact -- MySQL
# tracks the true per-digest maximum natively, not derived from the mean.
_QUERY_STATS_SQL = """
    SELECT SUM(COUNT_STAR) AS cnt, SUM(SUM_TIMER_WAIT) AS sum_wait, MAX(MAX_TIMER_WAIT) AS max_wait
    FROM performance_schema.events_statements_summary_by_digest
    WHERE COUNT_STAR > 0
"""

_SIZE_SQL = """
    SELECT TABLE_SCHEMA, SUM(DATA_LENGTH) AS data_len, SUM(INDEX_LENGTH) AS index_len
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
    GROUP BY TABLE_SCHEMA
"""

_DEADLOCKS_SQL = """
    SELECT SUM_ERROR_RAISED AS cnt
    FROM performance_schema.events_errors_summary_global_by_error
    WHERE ERROR_NAME = 'ER_LOCK_DEADLOCK'
"""

# picoseconds -> seconds, per performance_schema's TIMER_WAIT convention.
_PICOSECONDS_PER_SECOND = 1e12


class MysqlAdapter(VendorAdapter):
    def __init__(self, target: DatabaseTarget):
        super().__init__(target)

    def connect(self):
        conn = mysql.connector.connect(
            host=self.target.host,
            port=self.target.port,
            database=self.target.database,
            user=self.target.username,
            password=self.target.password,
            connection_timeout=self.target.scrape_timeout_seconds,
        )
        conn.autocommit = True  # read-only monitoring queries; no reason to hold a transaction open
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
            (
                "threads_connected",
                lambda: self._global_status_gauge(
                    conn, "Threads_connected", "mysql_global_status_threads_connected", "Global open connections."
                ),
            ),
            (
                "max_connections",
                lambda: self._global_variable_gauge(
                    conn, "max_connections", "mysql_global_variables_max_connections", "Configured max_connections."
                ),
            ),
            (
                "innodb_row_locks",
                lambda: self._global_status_gauge(
                    conn,
                    "Innodb_row_lock_current_waits",
                    "mysql_global_status_innodb_current_row_locks",
                    "Current InnoDB row-level lock waits.",
                ),
            ),
            ("deadlocks", lambda: self._deadlocks_family(conn)),
            ("size", lambda: self._size_family(conn)),
            ("replication_lag", lambda: self._replication_lag_family(conn)),
        ]
        for label, builder in queries:
            result_families, err = self.safe_collect_family(label, builder)
            families.extend(result_families)
            had_error = had_error or err
        return families, had_error

    def _query_duration_family(self, conn):
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(_QUERY_STATS_SQL)
            row = cur.fetchone()
        finally:
            cur.close()
        if not row or row["cnt"] is None:
            return build_query_stats_families(
                "mysql_perf_schema_events_statements_seconds", "Statement execution time from performance_schema", 0, 0.0, None
            )
        return build_query_stats_families(
            "mysql_perf_schema_events_statements_seconds",
            "Statement execution time from performance_schema",
            int(row["cnt"]),
            float(row["sum_wait"]) / _PICOSECONDS_PER_SECOND,
            float(row["max_wait"]) / _PICOSECONDS_PER_SECOND,
        )

    def _global_status_gauge(self, conn, status_name: str, metric_name: str, help_text: str):
        cur = conn.cursor()
        try:
            cur.execute("SHOW GLOBAL STATUS LIKE %s", (status_name,))
            row = cur.fetchone()
        finally:
            cur.close()
        family = GaugeMetricFamily(metric_name, help_text)
        family.add_metric([], float(row[1]) if row else 0.0)
        return family

    def _global_variable_gauge(self, conn, variable_name: str, metric_name: str, help_text: str):
        cur = conn.cursor()
        try:
            cur.execute("SHOW GLOBAL VARIABLES LIKE %s", (variable_name,))
            row = cur.fetchone()
        finally:
            cur.close()
        family = GaugeMetricFamily(metric_name, help_text)
        family.add_metric([], float(row[1]) if row else 0.0)
        return family

    def _replication_lag_family(self, conn):
        cur = conn.cursor(dictionary=True)
        try:
            # SHOW SLAVE STATUS is supported through MySQL 8.0 (deprecated alias
            # of SHOW REPLICA STATUS on 8.0.22+); use it for broad compatibility.
            cur.execute("SHOW SLAVE STATUS")
            row = cur.fetchone()
        finally:
            cur.close()
        if not row or row.get("Seconds_Behind_Master") is None:
            return None
        family = GaugeMetricFamily(
            "mysql_slave_status_seconds_behind_master", "Replica lag in seconds."
        )
        family.add_metric([], float(row["Seconds_Behind_Master"]))
        return family

    def _deadlocks_family(self, conn):
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(_DEADLOCKS_SQL)
            row = cur.fetchone()
        finally:
            cur.close()
        # GaugeMetricFamily, not CounterMetricFamily: Counter*Family auto-appends
        # "_total" to the exposed name, which would break the exact metric name
        # recording_rules/db_mysql.yml already expects.
        family = GaugeMetricFamily(
            "mysql_global_status_innodb_deadlocks", "Cumulative InnoDB deadlock count."
        )
        family.add_metric([], float(row["cnt"]) if row and row["cnt"] is not None else 0.0)
        return family

    def _size_family(self, conn):
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(_SIZE_SQL)
            rows = cur.fetchall()
        finally:
            cur.close()
        data_family = GaugeMetricFamily(
            "mysql_info_schema_table_size_data_length", "Data size per schema.", labels=["schema_name"]
        )
        index_family = GaugeMetricFamily(
            "mysql_info_schema_table_size_index_length", "Index size per schema.", labels=["schema_name"]
        )
        for row in rows:
            data_family.add_metric([row["TABLE_SCHEMA"]], row["data_len"] or 0)
            index_family.add_metric([row["TABLE_SCHEMA"]], row["index_len"] or 0)
        return [data_family, index_family]
