"""PostgreSQL collector.

Emits exactly the vendor-native metric names recording_rules/db_postgres.yml
already expects (db_type="postgres" filter is applied by Prometheus, not
here -- this module only needs to produce the raw metric names/labels).
"datname" is emitted as-is; the recording rule itself renames it to
"database", so this module must NOT do that rename.
"""
import psycopg2
import psycopg2.extras
from prometheus_client.core import GaugeMetricFamily

from src.collectors.base import VendorAdapter
from src.collectors.query_stats import build_query_stats_families
from src.config import DatabaseTarget

# count/sum are exact (plain sums). max_exec_time is also exact -- Postgres
# tracks the true per-digest maximum natively, not derived from the mean.
_QUERY_STATS_SQL = """
    SELECT SUM(calls) AS total_calls, SUM(total_exec_time) AS total_time, MAX(max_exec_time) AS max_time
    FROM pg_stat_statements
    WHERE calls > 0
"""

_ACTIVITY_SQL = """
    SELECT datname, count(*) AS cnt
    FROM pg_stat_activity
    WHERE datname IS NOT NULL
    GROUP BY datname
"""

_MAX_CONNECTIONS_SQL = "SELECT setting::int FROM pg_settings WHERE name = 'max_connections'"

_IS_REPLICA_SQL = "SELECT pg_is_in_recovery()"

_REPLICATION_LAG_SQL = """
    SELECT COALESCE(EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())), 0)
"""

_LOCKS_SQL = """
    SELECT d.datname, l.mode, count(*) AS cnt
    FROM pg_locks l
    JOIN pg_database d ON l.database = d.oid
    GROUP BY d.datname, l.mode
"""

_DEADLOCKS_SQL = "SELECT datname, deadlocks FROM pg_stat_database WHERE datname IS NOT NULL"

_SIZE_SQL = """
    SELECT datname, pg_database_size(datname)
    FROM pg_database
    WHERE datname NOT IN ('template0', 'template1')
"""


class PostgresAdapter(VendorAdapter):
    def __init__(self, target: DatabaseTarget):
        super().__init__(target)

    def connect(self):
        conn = psycopg2.connect(
            host=self.target.host,
            port=self.target.port,
            dbname=self.target.database,
            user=self.target.username,
            password=self.target.password,
            connect_timeout=self.target.scrape_timeout_seconds,
        )
        # Required for per-query error isolation in collect(): psycopg2
        # defaults to autocommit=False, so one failing query would otherwise
        # abort the whole transaction and cascade-fail every later query on
        # this same connection until a rollback. Autocommit makes each
        # statement independent -- correct anyway for read-only monitoring.
        conn.autocommit = True
        return conn

    def is_alive(self, conn) -> bool:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True

    def collect(self, conn) -> tuple[list, bool]:
        families: list = []
        had_error = False
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            queries = [
                ("query_duration", lambda: self._query_duration_family(cur)),
                ("activity", lambda: self._activity_family(cur)),
                ("max_connections", lambda: self._max_connections_family(cur)),
                ("replication_lag", lambda: self._replication_lag_family(cur)),
                ("locks", lambda: self._locks_family(cur)),
                ("deadlocks", lambda: self._deadlocks_family(cur)),
                ("size", lambda: self._size_family(cur)),
            ]
            for label, builder in queries:
                result_families, err = self.safe_collect_family(label, builder)
                families.extend(result_families)
                had_error = had_error or err
        return families, had_error

    def _query_duration_family(self, cur):
        cur.execute(_QUERY_STATS_SQL)
        row = cur.fetchone()
        if row is None or row["total_calls"] is None:
            return build_query_stats_families(
                "pg_stat_statements_total_exec_time", "Query execution time from pg_stat_statements", 0, 0.0, None
            )
        # pg_stat_statements times are in milliseconds; convert to seconds.
        return build_query_stats_families(
            "pg_stat_statements_total_exec_time",
            "Query execution time from pg_stat_statements",
            int(row["total_calls"]),
            float(row["total_time"]) / 1000.0,
            float(row["max_time"]) / 1000.0,
        )

    def _activity_family(self, cur):
        cur.execute(_ACTIVITY_SQL)
        family = GaugeMetricFamily(
            "pg_stat_activity_count", "Active connections per database.", labels=["datname"]
        )
        for row in cur.fetchall():
            family.add_metric([row["datname"]], row["cnt"])
        return family

    def _max_connections_family(self, cur):
        cur.execute(_MAX_CONNECTIONS_SQL)
        value = cur.fetchone()[0]
        family = GaugeMetricFamily("pg_settings_max_connections", "Configured max_connections.")
        family.add_metric([], value)
        return family

    def _replication_lag_family(self, cur):
        cur.execute(_IS_REPLICA_SQL)
        is_replica = cur.fetchone()[0]
        if not is_replica:
            return None
        cur.execute(_REPLICATION_LAG_SQL)
        lag_seconds = cur.fetchone()[0]
        family = GaugeMetricFamily("pg_replication_lag", "Replication apply lag in seconds.")
        family.add_metric([], float(lag_seconds))
        return family

    def _locks_family(self, cur):
        cur.execute(_LOCKS_SQL)
        family = GaugeMetricFamily(
            "pg_locks_count", "Current lock count by database and mode.", labels=["datname", "mode"]
        )
        for row in cur.fetchall():
            family.add_metric([row["datname"], row["mode"]], row["cnt"])
        return family

    def _deadlocks_family(self, cur):
        cur.execute(_DEADLOCKS_SQL)
        # GaugeMetricFamily, not CounterMetricFamily: Counter*Family auto-appends
        # "_total" to the exposed name, which would break the exact metric name
        # (no suffix) that recording_rules/db_postgres.yml already expects.
        # Prometheus doesn't enforce TYPE at query time, so rate() still works.
        family = GaugeMetricFamily(
            "pg_stat_database_deadlocks", "Deadlocks per database.", labels=["datname"]
        )
        for row in cur.fetchall():
            family.add_metric([row["datname"]], row["deadlocks"])
        return family

    def _size_family(self, cur):
        cur.execute(_SIZE_SQL)
        family = GaugeMetricFamily(
            "pg_database_size_bytes", "Database size in bytes.", labels=["datname"]
        )
        for row in cur.fetchall():
            family.add_metric([row[0]], row[1])
        return family
