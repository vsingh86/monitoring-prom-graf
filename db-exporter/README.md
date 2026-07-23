# db-exporter

A single Python service that scrapes PostgreSQL, MySQL, SQL Server, and
Oracle databases and exposes their metrics on `/metrics`, in a
blackbox_exporter-style multi-target design. Adding a new database instance
of an already-supported type is a config file entry, not a code change.

It exists because `../prometheus/recording_rules/db_{postgres,mysql,sqlserver,oracle}.yml`
already define exactly which vendor-native metric names to normalize into
the shared `db:*` schema the Grafana dashboards consume — but nothing
produced those metrics. This service produces them directly (real SQL
against each vendor's system catalog), so those recording rules and the
dashboards need **zero changes**.

## Quick start

```powershell
# from the repo root
cp .env.example .env                                 # fill in real passwords
cp db-exporter/config.example.yaml db-exporter/config.yaml   # fill in real hosts/users
docker compose up -d --build db-exporter
curl http://localhost:9433/health
curl http://localhost:9433/metrics?target=authapi-postgres
```

Then uncomment/point the matching `job_name` block in `../prometheus/prometheus.yml`
at this service (already wired for the example `authapi-postgres` /
`myapp-mysql` / `myapp-sqlserver` / `myapp-oracle` names) and reload
Prometheus.

## Adding a database

1. Add an entry to `db-exporter/config.yaml` (see `config.example.yaml` for
   the shape). Its `name` field is the join key used in three places — it
   must be identical to:
   - this config entry's `name`
   - the matching Prometheus job's `params.target` in `prometheus.yml`
   - the `app`/`db_type` labels stay a Prometheus-side concern (see the
     `centralized-monitoring/docs/onboarding-new-app.md` `app` label
     convention) — this config file never needs an `app` field.
2. Add the entry's `${ENV_VAR}` password to the repo-root `.env` file (copy
   from `.env.example` if you haven't already).
3. If it's a **new** password variable name, add a matching line to
   `docker-compose.yml`'s `db-exporter` service `environment:` block —
   Compose doesn't pass through arbitrary root-`.env` variables automatically,
   only the ones explicitly listed there.
4. Add/verify a Prometheus `job_name` block for it (see `prometheus.yml`'s
   `## Database exporters` section) with `params.target` matching step 1's
   `name`, plus `db_type` and `app` labels as usual.
5. `docker compose up -d --build db-exporter` (rebuild only needed if you
   changed code, not for config/`.env` changes — those are read at
   container start, so a plain restart is enough) then reload Prometheus.

Adding a **new vendor** (a 5th db_type) requires a new
`src/collectors/<vendor>.py` module plus a matching
`../prometheus/recording_rules/db_<vendor>.yml` — that's a code change, not
just a config entry.

## Troubleshooting: `db_exporter_up=0` / `db_exporter_scrape_error=1`

`/metrics?target=<name>` never returns a 500 or hangs on a database problem
— it returns 200 with `db_exporter_up{target}` and `db_exporter_scrape_error{target}`
signaling what happened, but the HTTP response itself never includes the
actual exception (only the exporter's own logs do). **Check the container
logs for the target name to see the real traceback.**

The most common real-world cause: **`ORA-00942: table or view does not
exist` (or the equivalent permission error on another vendor) almost always
means a missing grant, not a missing object.** Oracle in particular
deliberately reports "doesn't exist" instead of "no privilege" for `V$`
fixed views, to avoid confirming their existence to unauthorized users. See
"Required database grants" below and grant what's missing.

If only ONE query is failing (e.g. only `DBA_DATA_FILES` access is missing
after `SELECT_CATALOG_ROLE` was already granted), every other metric for
that target still gets collected and exposed normally — `collect()` isolates
each query independently (see "Known limitations" below), so `up` stays `1`
and only `scrape_error` goes to `1`. A `db_exporter_up=0` specifically means
the *connection itself* failed (network, credentials, DSN/service_name
typo), not just one query.

## Known limitations (by design, not oversights)

- **Oracle's query duration has no `_max` series.** `db:query_duration_seconds_count`/`_sum`/`_max`
  used to be an approximated histogram for all four vendors (each query
  digest's call count bucketed at its own mean, since none of these vendors
  expose a true per-call latency distribution). That's gone now — `count`
  and `sum` were always exact (plain sums) and stay exact; `max` is a new,
  also-exact metric sourced from each vendor's own native per-digest maximum
  column (Postgres `max_exec_time`, MySQL `MAX_TIMER_WAIT`, SQL Server
  `max_elapsed_time` — all tracked natively, not derived). Oracle's
  `v$sqlarea` has no equivalent column, and a true one would need licensed
  Diagnostics Pack features (AWR/ASH/SQL Monitoring) — rather than fake one,
  `oracle.py` simply omits `_max`, and the Grafana panel shows "No data" for
  Oracle's max series specifically. See `src/collectors/query_stats.py`.
- **Oracle `oracledb_deadlocks_total` is a proxy, not a true counter.**
  Oracle exposes no V$ view with a cumulative ORA-00060 count. The current
  implementation counts sessions live-blocked on `enq: TX - row lock
  contention` — a point-in-time gauge, not a monotonic counter. The
  recording rule applies `rate()` to it, which can produce misleading values
  when this gauge dips. A real fix means tailing the alert log/trace
  directory for ORA-00060 (needs a mounted volume) — not implemented.
- **A hung connection attempt leaks its worker thread.** The per-target
  timeout (`scrape_timeout_seconds`) stops *waiting* for a hung connect/query,
  but Python cannot forcibly kill a thread — the thread keeps running in the
  background. Repeated hangs against the same unreachable database can
  eventually exhaust the thread pool (default 8 workers). Acceptable for the
  current scale; would need process-level isolation to fix properly.
- **MySQL/SQL Server AG/replica-lag and Oracle Data Guard lag metrics are
  conditional.** They're only emitted when the instance is actually a
  replica/standby/AG member — otherwise the corresponding Grafana panel
  correctly shows "No data," matching the existing recording rules' own
  documented assumptions.

**Per-query error isolation:** each collector's `collect()` runs every query
independently via `VendorAdapter.safe_collect_family()` — one failing query
(missing grant, transient error, etc.) logs a warning and sets
`db_exporter_scrape_error=1`, but every other query's metrics still get
returned rather than the whole scrape coming back empty. `db_exporter_up`
only goes to `0` when the *connection itself* fails (see "Troubleshooting"
above) — a connected-but-partially-failing scrape reports `up=1,
scrape_error=1`. This also required setting `autocommit=True` on every
vendor's connection: without it (especially on Postgres, which aborts the
whole transaction on any statement error), one failed query would otherwise
poison every later query in the same scrape until a rollback, defeating the
isolation.

## Required database grants

- **Postgres**: `pg_stat_statements` extension enabled; read access to
  `pg_stat_activity`, `pg_locks`, `pg_stat_database`, `pg_database`.
- **MySQL**: `performance_schema` enabled; `SELECT` on
  `performance_schema.*` and `information_schema.TABLES`; `REPLICATION
  CLIENT` for `SHOW SLAVE STATUS`.
- **SQL Server**: `VIEW SERVER STATE` for the `sys.dm_*` dynamic management
  views used throughout.
- **Oracle**: `SELECT_CATALOG_ROLE` (or equivalent grants on `V_$SQLAREA`,
  `V_$RESOURCE_LIMIT`, `V_$LOCK`, `V_$SESSION`, `V_$DATABASE`,
  `V_$DATAGUARD_STATS`) plus `SELECT` on `DBA_DATA_FILES`.

All four connections should use a dedicated **read-only monitoring user** —
none of this service's queries write anything.

## Testing

```powershell
cd db-exporter
python -m venv .venv
./.venv/Scripts/pip install -r requirements-dev.txt
./.venv/Scripts/python -m pytest tests/ -v
```

Unit tests mock the DB-API driver layer (`tests/fakes.py`) — no live
databases are needed to run them.
