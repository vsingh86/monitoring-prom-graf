"""Oracle collector.

Emits exactly the vendor-native metric names recording_rules/db_oracle.yml
already expects -- that file's own comments state these require custom
queries that don't exist in any default exporter; this module supplies them.
Uses python-oracledb in thin mode (no Oracle Instant Client needed).

Known gap: oracledb_deadlocks_total is NOT a true cumulative ORA-00060 count
-- Oracle exposes no such counter via any V$ view. It's a point-in-time proxy
(current sessions blocked on 'enq: TX - row lock contention'), i.e. a GAUGE,
not a counter. The recording rule applies rate() to it expecting counter
semantics, so this proxy can produce misleading values on the "Deadlocks/s"
panel (rate() over a gauge that dips is not meaningful). A real fix requires
tailing the alert log/trace directory for ORA-00060 -- out of scope for v1,
tracked as a known follow-up (see db-exporter/README.md).

Known gap: oracledb_query_duration_seconds has no _max series. v$sqlarea
exposes cumulative elapsed_time/executions per SQL (exact count/sum), but no
per-call maximum -- a true max would need licensed Diagnostics Pack features
(AWR/ASH/SQL Monitoring). Rather than fake one, this collector simply omits
it; the Grafana panel shows "No data" for Oracle's max series specifically.
"""
import re

import oracledb
from prometheus_client.core import GaugeMetricFamily

from src.collectors.base import VendorAdapter
from src.collectors.query_stats import build_query_stats_families
from src.config import DatabaseTarget

# count/sum are exact (plain sums); no max column exists in v$sqlarea (see
# module docstring) so max_seconds=None is passed to build_query_stats_families.
_QUERY_STATS_SQL = "SELECT SUM(executions) AS total_execs, SUM(elapsed_time) AS total_time FROM v$sqlarea WHERE executions > 0"

_RESOURCE_LIMIT_SQL = (
    "SELECT resource_name, current_utilization, limit_value "
    "FROM v$resource_limit WHERE resource_name = 'sessions'"
)

_DATABASE_ROLE_SQL = "SELECT database_role FROM v$database"

_DATAGUARD_LAG_SQL = "SELECT value FROM v$dataguard_stats WHERE name = 'apply lag'"

_LOCKS_SQL = """
    SELECT DECODE(lmode,
        0, 'none', 1, 'null', 2, 'row-share', 3, 'row-exclusive',
        4, 'share', 5, 'share-row-exclusive', 6, 'exclusive', 'unknown'
    ) AS lock_mode, COUNT(*) AS cnt
    FROM v$lock
    WHERE lmode > 0
    GROUP BY lmode
"""

_DEADLOCK_PROXY_SQL = "SELECT COUNT(*) FROM v$session WHERE event = 'enq: TX - row lock contention'"

_TABLESPACE_SQL = "SELECT tablespace_name, SUM(bytes) AS bytes FROM dba_data_files GROUP BY tablespace_name"

# v$sqlarea.elapsed_time is in microseconds.
_MICROSECONDS_PER_SECOND = 1e6

_INTERVAL_PATTERN = re.compile(r"([+-])(\d+)\s+(\d+):(\d+):(\d+(?:\.\d+)?)")


def _parse_oracle_interval_seconds(value: str) -> float | None:
    """Parses Oracle's DAY TO SECOND interval text (e.g. '+00 00:00:05.123') into seconds."""
    match = _INTERVAL_PATTERN.match(value.strip())
    if not match:
        return None
    sign, days, hours, minutes, seconds = match.groups()
    total = int(days) * 86400 + int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    return -total if sign == "-" else total


class OracleAdapter(VendorAdapter):
    def __init__(self, target: DatabaseTarget):
        super().__init__(target)

    def connect(self):
        dsn = f"{self.target.host}:{self.target.port}/{self.target.service_name}"
        conn = oracledb.connect(
            user=self.target.username,
            password=self.target.password,
            dsn=dsn,
            tcp_connect_timeout=self.target.scrape_timeout_seconds,
        )
        conn.autocommit = True  # read-only monitoring queries; no reason to hold a transaction open
        return conn

    def is_alive(self, conn) -> bool:
        cur = conn.cursor()
        try:
            cur.execute("SELECT 1 FROM dual")
            cur.fetchone()
        finally:
            cur.close()
        return True

    def collect(self, conn) -> tuple[list, bool]:
        families: list = []
        had_error = False
        queries = [
            ("query_duration", lambda: self._query_duration_family(conn)),
            ("locks", lambda: self._locks_family(conn)),
            ("deadlock_proxy", lambda: self._deadlock_proxy_family(conn)),
            ("tablespace", lambda: self._tablespace_family(conn)),
            ("resource_limits", lambda: self._resource_limit_families(conn)),
            ("dataguard_lag", lambda: self._dataguard_lag_family(conn)),
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
                "oracledb_query_duration_seconds", "Query execution time from v$sqlarea", 0, 0.0, None
            )
        total_execs, total_time = row
        return build_query_stats_families(
            "oracledb_query_duration_seconds",
            "Query execution time from v$sqlarea",
            int(total_execs),
            float(total_time) / _MICROSECONDS_PER_SECOND,
            None,  # no free exact max source on Oracle -- see module docstring
        )

    def _resource_limit_families(self, conn):
        cur = conn.cursor()
        try:
            cur.execute(_RESOURCE_LIMIT_SQL)
            row = cur.fetchone()
        finally:
            cur.close()

        current_family = GaugeMetricFamily(
            "oracledb_resource_current_utilization", "Current utilization from v$resource_limit.", labels=["resource_name"]
        )
        limit_family = GaugeMetricFamily(
            "oracledb_resource_limit_value", "Configured limit from v$resource_limit (-1 = UNLIMITED).", labels=["resource_name"]
        )
        if row:
            resource_name, current_utilization, limit_value = row
            current_family.add_metric([resource_name], float(current_utilization))
            limit_family.add_metric(
                [resource_name],
                -1.0 if str(limit_value).strip().upper() == "UNLIMITED" else float(limit_value),
            )
        return [current_family, limit_family]

    def _dataguard_lag_family(self, conn):
        cur = conn.cursor()
        try:
            cur.execute(_DATABASE_ROLE_SQL)
            role = cur.fetchone()[0]
            if role != "PHYSICAL STANDBY":
                return None
            cur.execute(_DATAGUARD_LAG_SQL)
            row = cur.fetchone()
        finally:
            cur.close()
        if not row:
            return None
        lag_seconds = _parse_oracle_interval_seconds(str(row[0]))
        if lag_seconds is None:
            return None
        family = GaugeMetricFamily("oracledb_dataguard_apply_lag_seconds", "Data Guard apply lag in seconds.")
        family.add_metric([], lag_seconds)
        return family

    def _locks_family(self, conn):
        cur = conn.cursor()
        try:
            cur.execute(_LOCKS_SQL)
            rows = cur.fetchall()
        finally:
            cur.close()
        family = GaugeMetricFamily("oracledb_locks_total", "Current lock count by mode.", labels=["mode"])
        for lock_mode, cnt in rows:
            family.add_metric([lock_mode], cnt)
        return family

    def _deadlock_proxy_family(self, conn):
        cur = conn.cursor()
        try:
            cur.execute(_DEADLOCK_PROXY_SQL)
            count = cur.fetchone()[0]
        finally:
            cur.close()
        # See module docstring: this is a point-in-time proxy, not a true
        # cumulative ORA-00060 counter.
        family = GaugeMetricFamily(
            "oracledb_deadlocks_total",
            "Proxy: sessions currently blocked on row lock contention (NOT a true deadlock counter).",
        )
        family.add_metric([], count)
        return family

    def _tablespace_family(self, conn):
        cur = conn.cursor()
        try:
            cur.execute(_TABLESPACE_SQL)
            rows = cur.fetchall()
        finally:
            cur.close()
        family = GaugeMetricFamily(
            "oracledb_tablespace_bytes", "Tablespace size in bytes.", labels=["tablespace"]
        )
        for tablespace_name, size_bytes in rows:
            family.add_metric([tablespace_name], size_bytes)
        return family
