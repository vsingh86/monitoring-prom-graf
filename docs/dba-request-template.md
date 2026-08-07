# DBA request template: read-only monitoring user

A fill-in-the-blank draft for the ServiceHub change request that asks a
DBA to create the read-only monitoring user `db-exporter` connects as.
Copy the relevant sections into your ServiceHub ticket, fill in the
brackets, and attach the one SQL script matching your database vendor.

One request per database instance/target — if an app has both a
Postgres primary and a read replica, or multiple databases on one
instance you want monitored, file one request per instance (the account
setup is identical each time, just re-run against each target).

---

## ServiceHub ticket fields

**Request type:** Database change / new account request (whichever
ServiceHub category your DBA team uses for account provisioning — not a
data change, not an access request for a human user)

**Priority:** Standard (this is not time-sensitive/production-impacting —
don't request Expedited unless there's a specific deadline)

**Short description:**
> New read-only monitoring user for `[APP NAME]`'s `[postgres|mysql|sqlserver|oracle]`
> database — centralized monitoring platform (db-exporter)

**Affected system/instance:**
> `[hostname:port / instance name]`, database `[database name]`

---

## Ticket body (copy/paste, fill in brackets)

```
Requesting a new database user for automated, read-only metrics
collection. This user will be used exclusively by a monitoring service
(db-exporter) that scrapes query performance stats, connection counts,
lock/deadlock counts, and database size on a ~15-second interval. It does
not and will never write, and does not need access to any application
data or tables — only to the database engine's own system/performance
views.

Requested:
- New login/user: prom_exporter (or your team's preferred naming — the
  name itself doesn't matter, only the grants below do)
- Password: [we will provide a generated password via <secrets channel>,
  not in this ticket] -- or -- [please generate and share via <secrets
  channel>]
- Target: [hostname:port], database/instance [name]
- Grants: exactly as specified in the attached script -- no more, no
  less. See "What this user can and cannot do" below.

Attached: [postgres|mysql|sqlserver|oracle]_create_user.sql
(from db-exporter/sql/ in the monitoring platform repo)

Requested by: [name/team]
App this supports: [App Name] ([Team/Division])
Target go-live / needed by: [date, or "no specific deadline"]
```

---

## What this user can and cannot do (include this — DBAs will ask)

**Can:** read the database engine's own performance/system views — query
statistics, active session and connection counts, lock and deadlock
counts, replication/AG lag (if applicable), tablespace/database size.
Nothing here is application data.

**Cannot:** read, write, or modify any application table, view, or data.
Cannot create/alter/drop objects. Cannot execute stored procedures. This
is enforced by the grants themselves, not by convention — the attached
script grants nothing beyond the specific system views/roles listed
below.

**Cannot:** log in interactively / isn't used by any human — only the
`db-exporter` service (deployed by the platform team) authenticates as
this user, on an automated schedule.

## Per-vendor grant summary (pick the one matching your target)

| Vendor | Script to attach | Grants requested | What they cover |
|---|---|---|---|
| PostgreSQL | `postgres_create_user.sql` | `pg_monitor` role; `CONNECT` on the target database; `SELECT` on `pg_stat_statements` | `pg_stat_activity`, `pg_settings`, replication status, query duration stats. Requires `pg_stat_statements` already loaded via `shared_preload_libraries` (a server restart is needed if it isn't — flag this to the DBA up front, it's the one grant that isn't just a `GRANT` statement). |
| MySQL | `mysql_create_user.sql` | `SELECT` on `performance_schema.*` and `information_schema.*`; `REPLICATION CLIENT` | Query digest stats, deadlock counter, per-schema table/index size, replica lag (`SHOW SLAVE STATUS`). Requires `performance_schema=ON` already set in `my.cnf` — flag this too if unknown. |
| SQL Server | `sqlserver_create_user.sql` | `VIEW SERVER STATE`; `CONNECT SQL` | Every `sys.dm_*` dynamic management view used (query stats, sessions, locks, waiting tasks, perf counters, AG replica state). **Azure SQL Database (not Managed Instance)** has no server-level DMVs — grant `VIEW DATABASE STATE` in the target database instead and expect the AG/replica-lag panel to show "No data"; call this out in the ticket if the target is Azure SQL DB. |
| Oracle | `oracle_create_user.sql` | `CREATE SESSION`; `SELECT_CATALOG_ROLE`; `SELECT` on `DBA_DATA_FILES` | `V_$SQLAREA`, `V_$RESOURCE_LIMIT`, `V_$LOCK`, `V_$SESSION`, `V_$DATABASE`, `V_$DATAGUARD_STATS`, plus tablespace size. On a multitenant (CDB/PDB) database, the DBA needs to run this connected to the target PDB (`ALTER SESSION SET CONTAINER = <pdb_name>;` first) — note the PDB name in the ticket. |

Full grant rationale (which query needs which grant) is documented inline
in each script and in [`db-exporter/README.md`](../db-exporter/README.md#required-database-grants)
if a DBA wants to review before approving.

## After the DBA runs the script

Don't close the ticket yet — verify the grants actually work before
calling this done. Run the matching `<vendor>_verify_grants.sql` script
(same `db-exporter/sql/` directory) **logged in as the new monitoring
user** — every query in it should succeed. This catches a missing or
misspelled grant now, instead of it surfacing later as a silently blank
panel on a dashboard (see `db-exporter/README.md`'s troubleshooting
section — a missing grant on Oracle in particular reports "table or view
does not exist" rather than a permission error, which is easy to
misdiagnose after the fact).

Once verified, hand the platform team: hostname:port, database/instance
name, the username, and where the password lives (a secret store —
never paste it into the ServiceHub ticket text or an email). This
matches what [`onboarding-consumer-app.md`](onboarding-consumer-app.md)
step 3/4 asks for.
