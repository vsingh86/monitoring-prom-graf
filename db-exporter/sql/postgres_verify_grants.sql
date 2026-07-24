-- Run each query below in a database editor while connected AS the
-- monitoring user created by postgres_create_user.sql, against the actual
-- target database. Every query must succeed (even if it returns zero rows)
-- -- any permission error here is exactly what db-exporter will hit in
-- production. Queries copied verbatim from src/collectors/postgres.py.

-- Backs: db:query_duration_seconds_{count,sum,max}
-- Requires: SELECT ON pg_stat_statements
SELECT SUM(calls) AS total_calls, SUM(total_exec_time) AS total_time, MAX(max_exec_time) AS max_time
FROM pg_stat_statements
WHERE calls > 0;

-- Backs: db:connections_active
-- Requires: pg_monitor
SELECT datname, count(*) AS cnt
FROM pg_stat_activity
WHERE datname IS NOT NULL AND datname != 'rdsadmin'
GROUP BY datname;

-- Backs: db:connections_max
-- Requires: pg_monitor
SELECT setting::int FROM pg_settings WHERE name = 'max_connections';

-- Backs: db:replication_lag_seconds (only emitted when this is a replica)
-- Requires: pg_monitor
SELECT pg_is_in_recovery();
SELECT COALESCE(EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())), 0);

-- Backs: db:locks_total
-- Requires: pg_monitor (pg_locks/pg_database are world-readable by default)
SELECT d.datname, l.mode, count(*) AS cnt
FROM pg_locks l
JOIN pg_database d ON l.database = d.oid
WHERE d.datname != 'rdsadmin'
GROUP BY d.datname, l.mode;

-- Backs: db:deadlocks_total
-- Requires: pg_monitor
SELECT datname, deadlocks
FROM pg_stat_database
WHERE datname IS NOT NULL AND datname != 'rdsadmin';

-- Backs: db:size_bytes
-- Requires: CONNECT on every database this returns (rdsadmin deliberately
-- excluded -- see the comment in postgres.py's _SIZE_SQL)
SELECT datname, pg_database_size(datname)
FROM pg_database
WHERE datname NOT IN ('template0', 'template1', 'rdsadmin');
