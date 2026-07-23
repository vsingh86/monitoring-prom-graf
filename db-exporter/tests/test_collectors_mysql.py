from src.collectors.mysql import MysqlAdapter
from src.config import DatabaseTarget
from tests.fakes import FakeConnection, build_registry, metric_lines

TARGET = DatabaseTarget(
    name="myapp-mysql",
    db_type="mysql",
    host="mysql-host",
    port=3306,
    username="u",
    password="p",
    database="myapp",
)


def test_collect_happy_path_is_replica():
    queue = [
        # 1. query stats (aggregate row; picoseconds)
        [{"cnt": 20, "sum_wait": 20 * 0.05 * 1e12, "max_wait": 0.2 * 1e12}],
        # 2. Threads_connected
        [("Threads_connected", "7")],
        # 3. max_connections
        [("max_connections", "151")],
        # 4. Innodb_row_lock_current_waits
        [("Innodb_row_lock_current_waits", "2")],
        # 5. deadlocks
        [{"cnt": 3}],
        # 6. size per schema
        [{"TABLE_SCHEMA": "myapp", "data_len": 1000, "index_len": 200}],
        # 7. replication lag
        [{"Seconds_Behind_Master": 4}],
    ]
    conn = FakeConnection(queue)
    adapter = MysqlAdapter(TARGET)

    families, had_error = adapter.collect(conn)
    text = metric_lines(build_registry(families))

    assert "mysql_perf_schema_events_statements_seconds_count 20.0" in text
    assert "mysql_perf_schema_events_statements_seconds_max 0.2" in text
    assert "mysql_global_status_threads_connected 7.0" in text
    assert "mysql_global_variables_max_connections 151.0" in text
    assert "mysql_global_status_innodb_current_row_locks 2.0" in text
    assert "mysql_global_status_innodb_deadlocks 3.0" in text
    assert 'mysql_info_schema_table_size_data_length{schema_name="myapp"} 1000.0' in text
    assert 'mysql_info_schema_table_size_index_length{schema_name="myapp"} 200.0' in text
    assert "mysql_slave_status_seconds_behind_master 4.0" in text
    assert had_error is False


def test_one_failing_query_does_not_discard_the_others():
    queue = [
        RuntimeError("access denied for performance_schema"),  # query_duration fails
        [("Threads_connected", "7")],
        [("max_connections", "151")],
        [("Innodb_row_lock_current_waits", "2")],
        [{"cnt": 3}],
        [{"TABLE_SCHEMA": "myapp", "data_len": 1000, "index_len": 200}],
        [],  # not a replica
    ]
    conn = FakeConnection(queue)
    adapter = MysqlAdapter(TARGET)

    families, had_error = adapter.collect(conn)
    text = metric_lines(build_registry(families))

    assert had_error is True
    assert "mysql_perf_schema_events_statements_seconds" not in text
    assert "mysql_global_status_threads_connected 7.0" in text
    assert "mysql_global_status_innodb_deadlocks 3.0" in text
    assert 'mysql_info_schema_table_size_data_length{schema_name="myapp"} 1000.0' in text


def test_collect_not_a_replica_omits_lag_metric():
    queue = [
        # A no-GROUP-BY aggregate query always returns exactly one row, with
        # NULLs when nothing matches WHERE COUNT_STAR > 0 -- not an empty result.
        [{"cnt": None, "sum_wait": None, "max_wait": None}],
        [("Threads_connected", "1")],
        [("max_connections", "151")],
        [("Innodb_row_lock_current_waits", "0")],
        [{"cnt": 0}],
        [],  # size
        [],  # SHOW SLAVE STATUS -- empty result set, not a replica
    ]
    conn = FakeConnection(queue)
    adapter = MysqlAdapter(TARGET)

    families, had_error = adapter.collect(conn)
    text = metric_lines(build_registry(families))

    assert "mysql_slave_status_seconds_behind_master" not in text
    assert "mysql_perf_schema_events_statements_seconds_count 0.0" in text
    assert "mysql_perf_schema_events_statements_seconds_max" not in text
