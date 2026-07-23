-- Read-only monitoring user for db-exporter (Oracle).
-- Run as a DBA-privileged user. On a multitenant (CDB/PDB) database, connect
-- to the target PDB first (ALTER SESSION SET CONTAINER = <pdb_name>;).
--
-- Grants map directly to the queries in src/collectors/oracle.py:
--   SELECT_CATALOG_ROLE -> V_$SQLAREA, V_$RESOURCE_LIMIT, V_$LOCK,
--                          V_$SESSION, V_$DATABASE, V_$DATAGUARD_STATS
--   SELECT ON DBA_DATA_FILES -> tablespace size (not covered by the role above)

CREATE USER db_exporter IDENTIFIED BY "CHANGE_ME";

GRANT CREATE SESSION TO db_exporter;
GRANT SELECT_CATALOG_ROLE TO db_exporter;
GRANT SELECT ON DBA_DATA_FILES TO db_exporter;
