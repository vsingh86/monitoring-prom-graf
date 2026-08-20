# Project Context

Centralized Prometheus + Grafana monitoring stack that scrapes applications
and their databases across multiple teams/divisions, with normalized
dashboards that work across tech stacks without per-app customization.

> `README.md` is stale (references old paths: `recording_rules/`,
> `grafana/dashboards/`, etc. from before a mid-project restructure). Trust
> this file and the actual directory layout over it.

## Architecture

- Prometheus scrapes application `/metrics` endpoints directly, host
  exporters (`node_exporter`/`windows_exporter`) for infra, and
  `db-exporter` (a custom Python service in this repo) for database
  metrics.
- Recording rules (`prometheus/rules/data-mapping/*.yml`) normalize each
  vendor/stack's native metric names into three shared schemas: `app:*`
  (HTTP request/latency), `db:*` (database), `host:*` (infra). Grafana
  dashboards only ever query the normalized names, never raw vendor
  metrics — so the same dashboard works across Node.js/.NET/.NET
  Framework/Java and Postgres/MySQL/SQL Server/Oracle with zero
  per-app customization.
- Grafana dashboards are generic, driven by template variables, and come in
  two families, both anchored on a single top-level `$app` variable — every
  other variable (`$job`, `$host_job`, `$db_job`, `$frontend_job`,
  `$backend_job`, `$frontend_host_job`, `$backend_host_job`) is hidden and
  derived from `$app` + the `component` label below. The **2-tier family**
  (single app job: app + optional host + optional db) picks its one app
  job via `component="app"`. The **3-tier family** (a genuine
  frontend/backend split) picks four via `component="frontend-app"` /
  `"backend-app"` / `"frontend-host"` / `"backend-host"`. Every link into
  a `core/` dashboard from elsewhere (team-overview cards, etc.) uses
  `var-app=<AppName>` — **never `var-job`** — this used to be split
  (`var-job` for 2-tier, `var-app` for 3-tier) and that inconsistency
  caused a real bug (a team-overview card silently defaulted to the wrong
  app because it used the other family's URL param). Onboarding a new app
  should require **zero dashboard edits** — only new scrape-config files
  plus the label conventions below, `component` included.

## Key label conventions (every scrape job must set)

- `app` — PascalCase app name (e.g. `HIMS`, `AuthApi`). The join key tying
  an app's request/db/infra metrics together across jobs.
- `team` — must exactly match the destination Grafana folder's display
  name, e.g. `"HR and Finance"`, `"Public Safety"`, `"Middleware"` (quote
  in YAML — these contain spaces). Powers the Directors rollup dashboard's
  live per-team app count.
- `app_type` — `nodejs` | `dotnet` | `dotnet-framework` | `java`. Selects
  which `rules/data-mapping/<stack>.yml` normalizes this job's HTTP
  metrics. **`dotnet` and `dotnet-framework` are not interchangeable** —
  incompatible native metric names (`dotnet` assumes OTel ASP.NET Core;
  `dotnet-framework` assumes manual `prometheus-net` instrumentation).
- `db_type` — `postgres` | `mysql` | `sqlserver` | `oracle`. Selects
  `rules/data-mapping/db_<type>.yml`.
- `host_type` — `linux` | `windows`. Selects `infra_linux.yml` /
  `infra_windows.yml`.
- `component` — **required on every job, no exceptions**: `app` |
  `frontend-app` | `backend-app` | `host` | `frontend-host` |
  `backend-host` | `database`. This is the single label every dashboard
  variable reads to find "the job that plays this role for `$app`" —
  `label_values(up{app="$app", component="frontend-app"}, job)` — so
  `$app` alone is always enough to derive every job a dashboard needs, for
  both dashboard families. Single-tier apps (one HTTP-serving job — most
  apps, e.g. `AuthApi`, `CARD`) use the plain values `app`/`host`; apps
  with a genuine frontend/backend split (currently only `HIMS`) use the
  split values `frontend-app`/`backend-app`/`frontend-host`/
  `backend-host`. Database jobs always use `database` regardless of tier
  count. Use `app` (not `frontend-app`) for a single-tier app even if it's
  conceptually "the frontend" — some single-tier apps are a bare
  API/backend with no frontend at all (e.g. AuthApi), so `frontend-app`
  would be actively wrong for them. Job-name substrings are **not** a
  reliable way to infer role (CARD's only job is literally named
  `-frontend-` but it's its sole app job, not one half of a pair) — that's
  why this needs an explicit label rather than a naming convention.
  (Supersedes an earlier `tier: frontend|backend` label from a previous
  session — `tier` is fully retired, don't reintroduce it.)
- `environment` — `development` | `staging` | `production`.

`job_name` convention: `<division>-<app>-<component>-<env>` (e.g.
`hris-hims-app-backend-dev`) — an informal naming convention, not enforced
and not reliable to parse (see CARD/SCL Eng Std, whose job names don't
follow it). Don't confuse this positional `<component>` naming slot with
the actual required `component` **label** above — dashboards read the
label, never the job name.

## Directory layout

- `prometheus/prometheus.yml` — thin root config (global/alerting/
  rule_files/scrape_config_files only, no inline scrape jobs).
- `prometheus/scrape_configs/_platform.yml` — jobs with no single owning
  app (currently just Prometheus's own self-scrape).
- `prometheus/scrape_configs/<team-dir>/<app>/<env>.yml` — real per-app,
  per-environment scrape jobs. **Each file needs a top-level
  `scrape_configs:` key**, not a bare list — Prometheus's
  `scrape_config_files` unmarshals each file into a struct wrapping that
  key (confirmed against a real runtime error, not just docs). Currently
  only `hris/` exists as a team directory — that's the scrape-config dir
  *slug*; the team's actual Grafana folder/display name is "HR and
  Finance". Slug and display name don't have to match.
- **Critical Prometheus gotcha**: both `scrape_config_files` and
  `rule_files` reject a glob's `*` anywhere except the *final* path
  segment — a directory-level wildcard (`scrape_configs/*/*/*.yml`,
  `rules/alerts/*/*`) fails at startup ("invalid scrape/rule config file
  path"). Every app/team needs its own explicit line in `prometheus.yml`;
  a single pattern can't auto-discover new app/team directories.
- `prometheus/rules/data-mapping/*.yml` — recording rules, one file per
  tech-stack/db-vendor, normalizing to `app:*`/`db:*`/`host:*`.
- `prometheus/rules/alerts/<app>/*.yml` — alert rules, one explicit
  `rule_files` line per directory (same glob restriction as above).
- `db-exporter/` — custom Python service, blackbox_exporter-style: one
  shared process scrapes Postgres/MySQL/SQL Server/Oracle; Prometheus
  selects which DB via `?target=<name>` matching an entry in
  `db-exporter/config.yaml` (gitignored — copy from `config.example.yaml`).
  Real SQL against each vendor's own stats views; see
  `db-exporter/README.md` for known limitations (no true histogram, the
  Oracle deadlock counter is a proxy, etc).
  - `db-exporter/sql/<vendor>_create_user.sql` — least-privilege
    monitoring user setup per vendor.
  - `db-exporter/sql/<vendor>_verify_grants.sql` — the exact queries the
    collector runs, for a DBA to test directly without running the
    Python service.
  - Every per-database query is scoped to `config.yaml`'s `database:`
    field via a query parameter — **not** a blacklist of known system
    databases (`rdsadmin`, etc.). A blacklist doesn't scale and still
    misses other real databases sharing the same instance.
- `grafana/provisioning/dashboards/`:
  - `core/` — shared dashboards linked into from every team. Two families,
    both uid = filename, both landing in Grafana's General folder (no
    `folder:` key on this provider):
    - **2-tier family** (single app job, scoped by `$app`, `$job` hidden
      and derived via `component="app"`): `2-tier-fullstack-analytics.json`
      (app + host + db, the full dashboard), `2-tier-no-host-analytics.json`
      (app + db, no infra row), `2-tier-no-db-analytics.json` (app + host,
      no database row), `2-tier-no-host-no-db-analytics.json` (app only —
      apps with no scrapable host and no database, e.g. fully
      vendor-hosted).
    - **3-tier family** (frontend/backend split via the `component` label,
      scoped by `$app`): `3-tier-fullstack-analytics.json` (frontend
      app+host, backend app+host, db), `3-tier-no-host-analytics.json`
      (frontend app, backend app, db — no host rows),
      `3-tier-no-db-analytics.json` (frontend app+host, backend app+host —
      no database row). Only HIMS has the real split-`component`-labeled
      data for this family today.
    - `authapi-analytics.json` — AuthApi-specific deep-dive, currently
      unlinked (its `specific_dashboard` back-reference feature is paused,
      see `docs/onboarding-new-app.md` step 7); its one static back-link
      points at `2-tier-fullstack-analytics`.
  - `<team-dir>/team-overview.json` — one per team, its own Grafana
    folder (folder-level dashboard RBAC is the goal). **Caveat**: folder
    permissions restrict which *dashboards* a user can open, not which
    *data* an open dashboard can query — the `core/` dashboards take an
    open `$app` param, so true data isolation needs Grafana Teams/row
    permissions configured in Grafana itself, not expressible in static
    provisioning JSON.
  - `directors/all-teams-overview.json` — live per-team app count via the
    `team` label, for leadership.
  - `dashboards.yml` — the single provisioning source of truth, one
    provider per folder. (`default.yml` was deleted — its path was never
    actually mounted by `docker-compose.yml`, fully dead.)
- `docs/onboarding-new-app.md` — platform team's checklist (wiring an
  already-prepared app into Prometheus/Grafana).
- `docs/onboarding-consumer-app.md` — app team's checklist (what to
  prepare *before* handoff: expose `/metrics` matching the recording
  rule's expected shape, install a host exporter if self-hosted, get DBA
  grants via the `db-exporter/sql/` scripts).

## Known gotchas hit this session (worth remembering)

- **Metric-shape mismatches silently produce "No data," not a scrape
  error.** `up{job=...}` shows `1` (scrape succeeded), but a recording
  rule only matches if metric names *and* labels match exactly. Hit
  twice: a `dotnet-framework` app using `prometheus-net.AspNetCore`'s
  stock `UseHttpMetrics()` middleware emitted `http_requests_received_total`/
  `code`, not the hand-rolled `http_requests_total`/`status_code` the rule
  expected (fixed by adding a third `or` branch to the rule); a SQL Server
  target had `db-exporter` working standalone but no Prometheus job
  pointed at it at all, so it never got scraped in the first place.
- **`connections_max: 0` means "unlimited," not zero** (SQL Server/Postgres
  convention). A naive `active/max` ratio panel divides by zero (`+Inf` in
  PromQL, renders as broken). Guard with `(db:connections_max{...} > 0)`
  and pair with an absolute-count panel as a fallback that's always
  populated.
- Config is split across many small files (`scrape_configs/`, `rules/`,
  dashboard JSON) — a single YAML/JSON typo or bad glob fails silently or
  breaks startup. Validate with `promtool check config`, and
  `json.load`/`yaml.safe_load` every changed file before calling something
  done.
- Two Grafana dashboard-provisioning providers loading files with the
  same `uid` into different folders collide silently. When touching
  `dashboards.yml`, confirm every provider's `path:` actually contains
  files and no two dashboards share a `uid`.

## Testing

`db-exporter/tests/` — pytest, mocks the DB-API driver layer via
`tests/fakes.py` (no live databases needed to run them). Vendor DB drivers
aren't in a default Python install:
```
pip install pytest psycopg2-binary mysql-connector-python oracledb pymssql prometheus_client pyyaml
python -m pytest tests/ -v
```

## Current state (as of this session)

Only one team has real onboarded apps: HR and Finance (scrape-config dir
slug `hris`) — HIMS, AuthApi, Card, SCLENGINEERINGS. Public Safety and
Middleware exist as Grafana folders/dashboards with placeholder-only cards
(`public-safety-app1..5`, `middleware-app1..5`) — no real scrape jobs yet.

HIMS is currently the only app with a genuine frontend/backend
`component` split (its frontend and backend jobs run as two IIS sites on
one physical host, `spuappwebdvl`, so its frontend-host and backend-host
layers in the 3-tier dashboards resolve to the same single infra job —
expected, not a bug). AuthApi, Card, and SCLENGINEERINGS each have only a
single app job (`component: app`) and use the 2-tier dashboard family.
