from src.collectors.postgres import PostgresAdapter
from src.config import DatabaseTarget
from tests.fakes import FakeConnection, build_registry, metric_lines

TARGET = DatabaseTarget(
    name="authapi-postgres",
    db_type="postgres",
    host="pg-host",
    port=5432,
    username="u",
    password="p",
    database="authapi",
)


def test_collect_happy_path_is_replica():
    queue = [
        # 1. query stats (aggregate row; times in milliseconds)
        [{"total_calls": 15, "total_time": 25500.0, "max_time": 6000.0}],
        # 2. activity
        [{"datname": "authapi", "cnt": 3}],
        # 3. max_connections -> fetchone()[0]
        [(100,)],
        # 4. pg_is_in_recovery() -> fetchone()[0]
        [(True,)],
        # 5. replication lag -> fetchone()[0]
        [(2.5,)],
        # 6. locks
        [{"datname": "authapi", "mode": "RowShareLock", "cnt": 2}],
        # 7. deadlocks
        [{"datname": "authapi", "deadlocks": 0}],
        # 8. size -> positional
        [("authapi", 123456789)],
    ]
    conn = FakeConnection(queue)
    adapter = PostgresAdapter(TARGET)

    families, had_error = adapter.collect(conn)
    text = metric_lines(build_registry(families))

    assert "pg_stat_statements_total_exec_time_count 15.0" in text
    assert "pg_stat_statements_total_exec_time_sum 25.5" in text
    assert "pg_stat_statements_total_exec_time_max 6.0" in text
    assert 'pg_stat_activity_count{datname="authapi"} 3.0' in text
    assert "pg_settings_max_connections 100.0" in text
    assert "pg_replication_lag 2.5" in text
    assert 'pg_locks_count{datname="authapi",mode="RowShareLock"} 2.0' in text
    assert 'pg_stat_database_deadlocks{datname="authapi"} 0.0' in text
    assert 'pg_database_size_bytes{datname="authapi"} 1.23456789e+08' in text
    assert had_error is False


def test_collect_not_a_replica_omits_lag_metric():
    queue = [
        # A no-GROUP-BY aggregate query always returns exactly one row, with
        # NULLs when nothing matches WHERE calls > 0 -- not an empty result set.
        [{"total_calls": None, "total_time": None, "max_time": None}],
        [],  # activity: no active connections
        [(100,)],  # max_connections
        [(False,)],  # pg_is_in_recovery() -> not a replica
        [{"datname": "authapi", "mode": "RowShareLock", "cnt": 0}][:0],  # locks: none
        [],  # deadlocks
        [],  # size
    ]
    conn = FakeConnection(queue)
    adapter = PostgresAdapter(TARGET)

    families, had_error = adapter.collect(conn)
    text = metric_lines(build_registry(families))

    assert "pg_replication_lag" not in text
    # No matching queries should still emit a valid zeroed count/sum, with max omitted entirely.
    assert "pg_stat_statements_total_exec_time_count 0.0" in text
    assert "pg_stat_statements_total_exec_time_sum 0.0" in text
    assert "pg_stat_statements_total_exec_time_max" not in text
    assert had_error is False


def test_one_failing_query_does_not_discard_the_others():
    """Regression test for the real ORA-00942-style failure this repo hit in
    production: a missing grant on ONE view must not wipe out every other
    metric that would otherwise have succeeded."""
    queue = [
        RuntimeError("permission denied for view pg_stat_statements"),  # query_duration fails
        [{"datname": "authapi", "cnt": 3}],  # activity
        [(100,)],  # max_connections
        [(False,)],  # pg_is_in_recovery()
        [{"datname": "authapi", "mode": "RowShareLock", "cnt": 2}],  # locks
        [{"datname": "authapi", "deadlocks": 0}],  # deadlocks
        [("authapi", 123456789)],  # size
    ]
    conn = FakeConnection(queue)
    adapter = PostgresAdapter(TARGET)

    families, had_error = adapter.collect(conn)
    text = metric_lines(build_registry(families))

    assert had_error is True
    assert "pg_stat_statements_total_exec_time" not in text
    assert 'pg_stat_activity_count{datname="authapi"} 3.0' in text
    assert "pg_settings_max_connections 100.0" in text
    assert 'pg_locks_count{datname="authapi",mode="RowShareLock"} 2.0' in text
    assert 'pg_database_size_bytes{datname="authapi"} 1.23456789e+08' in text
