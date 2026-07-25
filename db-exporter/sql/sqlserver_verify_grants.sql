-- Run each query below in a database editor while connected AS the login
-- created by sqlserver_create_user.sql. Every query must succeed (even if
-- it returns zero rows) -- any permission error here is exactly what
-- db-exporter will hit in production. Queries copied verbatim from
-- src/collectors/sqlserver.py -- replace target_database with the exact
-- value of config.yaml's "database:" field for this target.

-- Backs: db:query_duration_seconds_{count,sum,max}
-- Requires: VIEW SERVER STATE
-- Note: dbid comes from CROSS APPLY sys.dm_exec_sql_text() and can be NULL
-- for some ad-hoc plans -- this is a best-effort scope, not exact.
SELECT SUM(qs.execution_count) AS cnt, SUM(qs.total_elapsed_time) AS total_time, MAX(qs.max_elapsed_time) AS max_time
FROM sys.dm_exec_query_stats qs
CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) st
WHERE st.dbid = DB_ID('target_database') AND qs.execution_count > 0;

-- Backs: db:connections_active
-- Requires: VIEW SERVER STATE
SELECT DB_NAME(database_id) AS db, COUNT(*) AS cnt
FROM sys.dm_exec_sessions
WHERE database_id = DB_ID('target_database') AND is_user_process = 1
GROUP BY database_id;

-- Backs: db:connections_max
-- Requires: no special privilege (sys.configurations is publicly visible)
SELECT CAST(value_in_use AS INT) FROM sys.configurations WHERE name = 'user connections';

-- Backs: db:locks_total
-- Requires: VIEW SERVER STATE
SELECT DB_NAME(l.resource_database_id) AS db, COUNT(*) AS cnt
FROM sys.dm_tran_locks l
JOIN sys.dm_os_waiting_tasks wt ON l.lock_owner_address = wt.resource_address
WHERE l.resource_database_id = DB_ID('target_database') AND l.request_status = 'WAIT'
GROUP BY l.resource_database_id;

-- Backs: db:deadlocks_total
-- Requires: VIEW SERVER STATE
SELECT cntr_value
FROM sys.dm_os_performance_counters
WHERE counter_name = 'Number of Deadlocks/sec' AND instance_name = '_Total';

-- Backs: db:size_bytes
-- Requires: no special privilege (sys.master_files is publicly visible)
SELECT DB_NAME(database_id) AS db, SUM(CAST(size AS BIGINT) * 8 * 1024) AS bytes
FROM sys.master_files
WHERE database_id = DB_ID('target_database')
GROUP BY database_id;

-- Backs: db:replication_lag_seconds (only emitted on an AG-protected instance)
-- Requires: VIEW SERVER STATE
-- Intentionally instance-wide (worst-case across all AG-protected databases),
-- not scoped to target_database -- see the comment on _AG_LAG_SQL.
SELECT MAX(drs.log_send_queue_size / NULLIF(drs.log_send_rate, 0)) AS lag_seconds
FROM sys.dm_hadr_database_replica_states drs;
