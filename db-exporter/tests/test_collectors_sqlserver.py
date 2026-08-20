import pymssql

from src.collectors import sqlserver
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


def test_per_database_queries_are_scoped_to_target_database():
    """query_duration, connections, lock_waits, and size must filter on
    target.database via DB_ID(%s) rather than returning every database on
    the instance -- ag_lag is the one deliberate exception (see its own
    comment in sqlserver.py)."""
    queue = [
        [(1, 1, 1)],
        [("myapp", 1)],
        [(0,)],
        [("myapp", 1)],
        [(0.0,)],
        [("myapp", 1)],
        [(None,)],
    ]
    conn = FakeConnection(queue)
    adapter = SqlServerAdapter(TARGET)

    adapter.collect(conn)

    scoped_queries = [
        sqlserver._QUERY_STATS_SQL,
        sqlserver._CONNECTIONS_SQL,
        sqlserver._LOCK_WAITS_SQL,
        sqlserver._SIZE_SQL,
    ]
    for sql, params in conn.calls:
        if sql in scoped_queries:
            assert params == (TARGET.database,)
        elif sql == sqlserver._AG_LAG_SQL:
            assert params is None


def test_is_auth_error_detects_login_failed():
    adapter = SqlServerAdapter(TARGET)
    exc = pymssql.OperationalError("(18456, b\"Login failed for user 'u'.DB-Lib error message 20018\")")
    assert adapter.is_auth_error(exc) is True


def test_is_auth_error_ignores_network_failures():
    adapter = SqlServerAdapter(TARGET)
    exc = pymssql.OperationalError("Unable to connect: Adaptive Server is unavailable or does not exist")
    assert adapter.is_auth_error(exc) is False


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
