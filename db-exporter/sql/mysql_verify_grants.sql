-- Run each statement below in a database editor while connected AS the
-- monitoring user created by mysql_create_user.sql. Every statement must
-- succeed (even if it returns zero rows) -- any permission error here is
-- exactly what db-exporter will hit in production. Queries copied verbatim
-- from src/collectors/mysql.py -- replace target_database with the exact
-- value of config.yaml's "database:" field for this target.

-- Backs: db:query_duration_seconds_{count,sum,max}
-- Requires: SELECT ON performance_schema.*
SELECT SUM(COUNT_STAR) AS cnt, SUM(SUM_TIMER_WAIT) AS sum_wait, MAX(MAX_TIMER_WAIT) AS max_wait
FROM performance_schema.events_statements_summary_by_digest
WHERE SCHEMA_NAME = 'target_database' AND COUNT_STAR > 0;

-- Backs: db:connections_active
-- Requires: no special privilege (SHOW STATUS is unrestricted)
SHOW GLOBAL STATUS LIKE 'Threads_connected';

-- Backs: db:connections_max
-- Requires: no special privilege (SHOW VARIABLES is unrestricted)
SHOW GLOBAL VARIABLES LIKE 'max_connections';

-- Backs: db:locks_total
-- Requires: no special privilege
SHOW GLOBAL STATUS LIKE 'Innodb_row_lock_current_waits';

-- Backs: db:deadlocks_total
-- Requires: SELECT ON performance_schema.*
SELECT SUM_ERROR_RAISED AS cnt
FROM performance_schema.events_errors_summary_global_by_error
WHERE ERROR_NAME = 'ER_LOCK_DEADLOCK';

-- Backs: db:size_bytes
-- Requires: SELECT ON information_schema.*
SELECT TABLE_SCHEMA, SUM(DATA_LENGTH) AS data_len, SUM(INDEX_LENGTH) AS index_len
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'target_database'
GROUP BY TABLE_SCHEMA;

-- Backs: db:replication_lag_seconds (only emitted when this is a replica)
-- Requires: REPLICATION CLIENT
SHOW SLAVE STATUS;
