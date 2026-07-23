from src.collectors.sqlserver import SqlServerAdapter
from src.config import DatabaseTarget
from tests.fakes import FakeConnection, build_registry, metric_lines

TARGET = DatabaseTarget(
    name="myapp-sqlserver",
    db_type="sqlserver",
    host="mssql-host",
    port=1433,
    username="u",
    password="p",
    database="myapp",
)


def test_collect_happy_path_with_ag():
    queue = [
        # 1. query stats (aggregate row; microseconds): cnt, total_time, max_time
        [(20, 20 * 50_000, 200_000)],
        # 2. connections
        [("myapp", 5)],
        # 3. max_connections
        [(0,)],  # 0 = unlimited
        # 4. lock waits
        [("myapp", 1)],
        # 5. deadlocks/sec
        [(0.0,)],
        # 6. size
        [("myapp", 10485760)],
        # 7. AG lag (only queried last)
        [(3.5,)],
    ]
    conn = FakeConnection(queue)
    adapter = SqlServerAdapter(TARGET)

    families, had_error = adapter.collect(conn)
    text = metric_lines(build_registry(families))

    assert "mssql_query_execution_seconds_count 20.0" in text
    assert "mssql_query_execution_seconds_max 0.2" in text
    assert 'mssql_connections{db="myapp"} 5.0' in text
    assert "mssql_max_connections 0.0" in text
    assert 'mssql_lock_waits{db="myapp"} 1.0' in text
    assert "mssql_deadlocks_per_second 0.0" in text
    assert 'mssql_database_size_bytes{db="myapp"} 1.048576e+07' in text
    assert "mssql_availability_group_log_send_queue_seconds 3.5" in text
    assert had_error is False


def test_one_failing_query_does_not_discard_the_others():
    queue = [
        RuntimeError("permission denied on sys.dm_exec_query_stats"),  # query_duration fails
        [("myapp", 5)],  # connections
        [(0,)],  # max_connections
        [("myapp", 1)],  # lock waits
        [(0.0,)],  # deadlocks/sec
        [("myapp", 10485760)],  # size
        [(None,)],  # no AG
    ]
    conn = FakeConnection(queue)
    adapter = SqlServerAdapter(TARGET)

    families, had_error = adapter.collect(conn)
    text = metric_lines(build_registry(families))

    assert had_error is True
    assert "mssql_query_execution_seconds" not in text
    assert 'mssql_connections{db="myapp"} 5.0' in text
    assert 'mssql_database_size_bytes{db="myapp"} 1.048576e+07' in text


def test_collect_no_availability_groups_omits_lag_metric():
    queue = [
        # A no-GROUP-BY aggregate query always returns exactly one row, with
        # NULLs when nothing matches WHERE execution_count > 0.
        [(None, None, None)],
        [],  # connections
        [(100,)],  # max_connections
        [],  # lock waits
        [(0.0,)],  # deadlocks/sec
        [],  # size
        [(None,)],  # no AG rows -> MAX(...) over empty set is NULL
    ]
    conn = FakeConnection(queue)
    adapter = SqlServerAdapter(TARGET)

    families, had_error = adapter.collect(conn)
    text = metric_lines(build_registry(families))

    assert "mssql_availability_group_log_send_queue_seconds" not in text
    assert "mssql_query_execution_seconds_count 0.0" in text
    assert "mssql_query_execution_seconds_max" not in text
