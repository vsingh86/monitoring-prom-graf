-- Read-only monitoring user for db-exporter (PostgreSQL).
-- Run as a superuser against the target database.
--
-- pg_stat_statements must already be loaded via shared_preload_libraries in
-- postgresql.conf (a server restart is required after adding it there --
-- CREATE EXTENSION alone does not enable collection).
--
-- Grants map directly to the queries in src/collectors/postgres.py:
--   pg_monitor          -> pg_stat_activity, pg_settings, replication status
--                          (pg_locks/pg_database are world-readable by default)
--   SELECT pg_stat_statements -> query duration stats (not covered by pg_monitor)

CREATE USER prom_exporter WITH PASSWORD 'CHANGE_ME' NOINHERIT;

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

GRANT pg_monitor TO prom_exporter;
GRANT CONNECT ON DATABASE :"target_database" TO prom_exporter;
GRANT SELECT ON pg_stat_statements TO prom_exporter;
