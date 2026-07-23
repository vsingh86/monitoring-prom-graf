-- Read-only monitoring user for db-exporter (MySQL).
-- Run as a user with GRANT OPTION against the target server.
--
-- performance_schema must already be enabled (performance_schema=ON in
-- my.cnf) -- this only grants access to it, it does not turn it on.
--
-- Grants map directly to the queries in src/collectors/mysql.py:
--   SELECT ON performance_schema.* -> query digest stats, deadlock counter
--   SELECT ON information_schema.* -> per-schema table/index size
--   REPLICATION CLIENT             -> SHOW SLAVE STATUS (replica lag)
-- SHOW GLOBAL STATUS / SHOW GLOBAL VARIABLES need no extra privilege.

CREATE USER 'db_exporter'@'%' IDENTIFIED BY 'CHANGE_ME';

GRANT SELECT ON performance_schema.* TO 'db_exporter'@'%';
GRANT SELECT ON information_schema.* TO 'db_exporter'@'%';
GRANT REPLICATION CLIENT ON *.* TO 'db_exporter'@'%';

FLUSH PRIVILEGES;
