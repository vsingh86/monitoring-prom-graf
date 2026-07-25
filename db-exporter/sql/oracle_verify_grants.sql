-- Run each query below in a database editor while connected AS the user
-- created by oracle_create_user.sql. On a multitenant (CDB/PDB) database,
-- connect to the target PDB first. Every query must succeed (even if it
-- returns zero rows) -- ORA-00942 here means a missing grant, NOT a missing
-- object (Oracle deliberately reports V$ views this way to avoid confirming
-- their existence to unauthorized users -- see db-exporter/README.md's
-- Troubleshooting section). Queries copied verbatim from
-- src/collectors/oracle.py.

-- Backs: db:query_duration_seconds_{count,sum}
-- Requires: SELECT_CATALOG_ROLE (V_$SQLAREA)
SELECT SUM(executions) AS total_execs, SUM(elapsed_time) AS total_time
FROM v$sqlarea
WHERE executions > 0;

-- Backs: db:connections_active, db:connections_max
-- Requires: SELECT_CATALOG_ROLE (V_$RESOURCE_LIMIT)
SELECT resource_name, current_utilization, limit_value
FROM v$resource_limit
WHERE resource_name = 'sessions';

-- Backs: db:replication_lag_seconds (only emitted on a physical standby)
-- Requires: SELECT_CATALOG_ROLE (V_$DATABASE, V_$DATAGUARD_STATS)
SELECT database_role FROM v$database;
SELECT value FROM v$dataguard_stats WHERE name = 'apply lag';

-- Backs: db:locks_total
-- Requires: SELECT_CATALOG_ROLE (V_$LOCK)
SELECT DECODE(lmode,
    0, 'none', 1, 'null', 2, 'row-share', 3, 'row-exclusive',
    4, 'share', 5, 'share-row-exclusive', 6, 'exclusive', 'unknown'
) AS lock_mode, COUNT(*) AS cnt
FROM v$lock
WHERE lmode > 0
GROUP BY lmode;

-- Backs: db:deadlocks_total (proxy metric, not a true counter -- see
-- oracle.py's module docstring)
-- Requires: SELECT_CATALOG_ROLE (V_$SESSION)
SELECT COUNT(*) FROM v$session WHERE event = 'enq: TX - row lock contention';

-- Backs: db:size_bytes
-- Requires: SELECT ON DBA_DATA_FILES (not covered by SELECT_CATALOG_ROLE)
-- SYSTEM/SYSAUX/UNDOTBS* are excluded as not part of the application's data
-- -- if this instance renamed its undo tablespace away from the UNDOTBS%
-- default, adjust the filter accordingly.
SELECT tablespace_name, SUM(bytes) AS bytes
FROM dba_data_files
WHERE tablespace_name NOT IN ('SYSTEM', 'SYSAUX') AND tablespace_name NOT LIKE 'UNDOTBS%'
GROUP BY tablespace_name;
