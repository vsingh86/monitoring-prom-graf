-- Read-only monitoring login for db-exporter (SQL Server).
-- Run against the instance as sysadmin (or an equivalent role).
--
-- VIEW SERVER STATE covers every sys.dm_* view queried by
-- src/collectors/sqlserver.py (dm_exec_query_stats, dm_exec_sessions,
-- dm_tran_locks, dm_os_waiting_tasks, dm_os_performance_counters,
-- dm_hadr_database_replica_states); sys.configurations and sys.master_files
-- are readable by any login by default.
--
-- Azure SQL Database (not Managed Instance) has no server-level DMVs or
-- VIEW SERVER STATE -- grant VIEW DATABASE STATE in each target database
-- instead, and expect the AG/replica-lag panel to show "No data".

USE master;
GO

CREATE LOGIN db_exporter WITH PASSWORD = 'CHANGE_ME';
GRANT VIEW SERVER STATE TO db_exporter;
GRANT CONNECT SQL TO db_exporter;
GO

USE [target_database];
GO

CREATE USER db_exporter FOR LOGIN db_exporter;
GO
