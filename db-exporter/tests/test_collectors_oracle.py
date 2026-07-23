from src.collectors.oracle import OracleAdapter, _parse_oracle_interval_seconds
from src.config import DatabaseTarget
from tests.fakes import FakeConnection, build_registry, metric_lines

TARGET = DatabaseTarget(
    name="myapp-oracle",
    db_type="oracle",
    host="oracle-host",
    port=1521,
    username="u",
    password="p",
    service_name="ORCLPDB1",
)


def test_parse_oracle_interval_seconds():
    assert _parse_oracle_interval_seconds("+00 00:00:05") == 5.0
    assert _parse_oracle_interval_seconds("+01 02:03:04.5") == 1 * 86400 + 2 * 3600 + 3 * 60 + 4.5
    assert _parse_oracle_interval_seconds("-00 00:00:02") == -2.0
    assert _parse_oracle_interval_seconds("garbage") is None


def test_collect_happy_path_standby_unlimited_sessions():
    queue = [
        # 1. query stats (aggregate row; microseconds): total_execs, total_time
        [(10, 10 * 50_000)],
        # 2. locks
        [("row-exclusive", 4)],
        # 3. deadlock proxy
        [(0,)],
        # 4. tablespaces
        [("USERS", 524288000)],
        # 5. resource limit (sessions)
        [("sessions", 42, "UNLIMITED")],
        # 6. database role
        [("PHYSICAL STANDBY",)],
        # 7. dataguard apply lag
        [("+00 00:00:05",)],
    ]
    conn = FakeConnection(queue)
    adapter = OracleAdapter(TARGET)

    families, had_error = adapter.collect(conn)
    text = metric_lines(build_registry(families))

    assert "oracledb_query_duration_seconds_count 10.0" in text
    assert "oracledb_query_duration_seconds_sum 0.5" in text
    assert "oracledb_query_duration_seconds_max" not in text  # no free exact source on Oracle
    assert 'oracledb_locks_total{mode="row-exclusive"} 4.0' in text
    assert "oracledb_deadlocks_total 0.0" in text
    assert 'oracledb_tablespace_bytes{tablespace="USERS"} 5.24288e+08' in text
    assert 'oracledb_resource_current_utilization{resource_name="sessions"} 42.0' in text
    assert 'oracledb_resource_limit_value{resource_name="sessions"} -1.0' in text
    assert "oracledb_dataguard_apply_lag_seconds 5.0" in text
    assert had_error is False


def test_one_failing_query_does_not_discard_the_others():
    """Regression test for the real production failure this repo hit: a
    missing SELECT_CATALOG_ROLE grant caused ORA-00942 on v$sqlarea, which
    (before this fix) discarded every other metric for the whole scrape."""
    queue = [
        RuntimeError("ORA-00942: table or view does not exist"),  # query_duration fails
        [("row-exclusive", 4)],  # locks
        [(0,)],  # deadlock proxy
        [("USERS", 524288000)],  # tablespaces
        [("sessions", 42, "UNLIMITED")],  # resource limit
        [("PHYSICAL STANDBY",)],  # database role
        [("+00 00:00:05",)],  # dataguard apply lag
    ]
    conn = FakeConnection(queue)
    adapter = OracleAdapter(TARGET)

    families, had_error = adapter.collect(conn)
    text = metric_lines(build_registry(families))

    assert had_error is True
    assert "oracledb_query_duration_seconds" not in text
    assert 'oracledb_locks_total{mode="row-exclusive"} 4.0' in text
    assert "oracledb_deadlocks_total 0.0" in text
    assert 'oracledb_tablespace_bytes{tablespace="USERS"} 5.24288e+08' in text
    assert 'oracledb_resource_current_utilization{resource_name="sessions"} 42.0' in text
    assert "oracledb_dataguard_apply_lag_seconds 5.0" in text


def test_collect_primary_role_omits_lag_metric():
    queue = [
        # A no-GROUP-BY aggregate query always returns exactly one row, with
        # NULLs when nothing matches WHERE executions > 0.
        [(None, None)],
        [],  # locks
        [(0,)],  # deadlock proxy
        [],  # tablespaces
        [("sessions", 10, "300")],  # resource limit, numeric limit this time
        [("PRIMARY",)],  # not a standby -- dataguard lag query is never issued
    ]
    conn = FakeConnection(queue)
    adapter = OracleAdapter(TARGET)

    families, had_error = adapter.collect(conn)
    text = metric_lines(build_registry(families))

    assert "oracledb_dataguard_apply_lag_seconds" not in text
    assert 'oracledb_resource_limit_value{resource_name="sessions"} 300.0' in text
    assert "oracledb_query_duration_seconds_count 0.0" in text
