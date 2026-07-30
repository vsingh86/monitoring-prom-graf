# Onboarding a new app

Checklist for adding a new application to this monitoring stack so it shows
up correctly in `Application Analytics` (`app-analytics.json`) — Layer 1
(Golden Signals), Layer 2 (Infrastructure), Layer 3 (Application), and
Layer 4 (Database) — with no dashboard edits required.

## 1. Pick a team, an app, and `app`/`team` label values

Choose a unique app name (e.g. `AuthApi`, PascalCase to match existing
convention) and confirm which team/division directory it belongs under
(e.g. `hris` — the scrape-config directory slug doesn't have to match the
team's Grafana folder/display name exactly; `hris` is the directory for what
Grafana shows as the "HR and Finance" folder). **Every job that belongs to
this app — its application job, database job(s), and infra host job(s) —
must set both:**
- `app: <Name>` — the join key `app-analytics.json` uses internally to tie
  an application's request metrics, database metrics, and host metrics
  together. Skipping it, or using a different value on one of the jobs,
  means that job's data won't show up when you select this app in the
  dashboard.
- `team: <Display Name>` — must exactly match the destination team's
  Grafana folder display name (e.g. `HR and Finance`, `Public Safety`,
  `Middleware`), quoted in YAML since these contain spaces
  (`team: "HR and Finance"`). This is what the Directors rollup dashboard
  (`directors/all-teams-overview.json`) counts per team — get it wrong and
  this app won't be counted (or gets miscounted) there.

Every scrape job lives under `prometheus/scrape_configs/<team>/<app>/<env>.yml`
(e.g. `prometheus/scrape_configs/hris/my-app/production.yml`). One file per
environment holds every job for that app in that environment (application,
database, infra).

Prometheus only allows a glob's `*` in the *final* path segment of a
`scrape_config_files`/`rule_files` entry, never in a directory component —
so a single `scrape_configs/*/*/*.yml`-style pattern that auto-discovers
brand new app directories isn't possible. Each app gets one explicit line in
`prometheus.yml`'s `scrape_config_files` (e.g. `scrape_configs/hris/my-app/*.yml`),
and in `rule_files` too if the app has its own alert rules directory.
**Adding a new environment for an app that's already onboarded is a
zero-edit change** — just add the file, the existing `*.yml` glob picks it
up automatically. Onboarding a brand new app still means adding those one or
two lines to `prometheus.yml`.

## 2. Add the application scrape job (required)

**If this app has never been onboarded before**, add one line to
`prometheus/prometheus.yml`'s `scrape_config_files` list:
`scrape_configs/<team>/<app>/*.yml` (see the comment above that list for why
a single auto-discovering glob isn't possible). Skip this if you're just
adding a new environment for an app that's already listed there.

Create (or add to) `prometheus/scrape_configs/<team>/<app>/<env>.yml`:

```yaml
scrape_configs:
  - job_name: my-app
    metrics_path: /metrics          # wherever the app exposes Prometheus metrics
    static_configs:
      - targets: ["my-app-host:port"]
        labels:
          app: MyApp
          team: "HR and Finance"     # exact Grafana folder display name -- see step 1
          app_type: nodejs           # or: dotnet, dotnet-framework, java
          environment: production
```

Each file needs its own top-level `scrape_configs:` key, same as the old
single-file layout — `scrape_config_files` merges the contents of every
matched file's `scrape_configs:` list, it doesn't accept a bare list.

`app_type` must match one of the existing `prometheus/rules/data-mapping/<stack>.yml`
files (`nodejs`, `dotnet`, `dotnet_framework`, `java`), which normalize that
stack's native HTTP metrics into the shared `app:*` schema the dashboard
queries. If your stack isn't one of these, add a new
`rules/data-mapping/<stack>.yml` following the same pattern (filter on
`app_type="<stack>"`, map native metric/label names to `app:*`) and
reference it under `rule_files:` in `prometheus.yml`.

> Note: `dotnet` (modern .NET + OpenTelemetry ASP.NET Core) and
> `dotnet-framework` (classic .NET Framework + `prometheus-net`) are separate
> `app_type` values because their native metric names are incompatible — pick
> based on how the app is actually instrumented, not just its language.

## 3. Add database job(s) — optional, only if Layer 4 applies

All four database types are served by one shared service,
[`db-exporter`](../db-exporter/README.md) — Prometheus doesn't scrape the
database directly, it scrapes `db-exporter` with a `params.target` selecting
which configured database to query (blackbox_exporter-style). Add this as
another item under the same file's `scrape_configs:` list from step 2:

```yaml
  - job_name: my-app-postgres
    params:
      target: ["my-app-postgres"]   # must match a "name:" entry in db-exporter/config.yaml
    static_configs:
      - targets: ["db-exporter:9433"]
        labels:
          app: MyApp                # same value as step 1
          team: "HR and Finance"    # same value as step 1
          db_type: postgres         # or: mysql, sqlserver, oracle
          environment: production
    relabel_configs:
      - source_labels: [__param_target]
        target_label: instance
```

You also need to add the actual connection details to
`db-exporter/config.yaml` (and its password to the repo-root `.env`) — see
[`db-exporter/README.md`](../db-exporter/README.md#adding-a-database) for
the full steps. `db_type` must match an existing `rules/data-mapping/db_<type>.yml`
(`postgres`, `mysql`, `sqlserver`, `oracle`), or a new one following the same
pattern (plus a new `db-exporter/src/collectors/<type>.py`). Also see
`db-exporter/sql/<type>_create_user.sql` and `<type>_verify_grants.sql` for
setting up and testing a least-privilege monitoring user for the new database.

## 4. Add infra host job(s) — optional, only if Layer 2 should scope to this app

One exporter job per host, again appended to the same `scrape_configs:`
list in the same `<team>/<app>/<env>.yml` file as steps 2-3:

```yaml
  - job_name: windows-exporter-my-app-host
    static_configs:
      - targets: ["my-app-host.example.com:9182"]
        labels:
          app: MyApp                # same value as step 1
          team: "HR and Finance"    # same value as step 1
          host_type: windows        # or: linux (node-exporter)
          environment: production
```

If this app has neither a database (step 3) nor a scrapable host (this step)
— e.g. fully vendor-hosted, no infra you can reach — skip both and use
`app-analytics-lite` instead of `app-analytics` when linking it from a
team-overview card (step 8). It's the same dashboard minus the Layer 2/4
rows and the saturation panel, so it doesn't show two permanently-empty
sections for an app that will never have that data.

If a host is shared across multiple apps, leave `app` off entirely — the
dashboard will correctly show no infra data for it under any single app's
view rather than attributing a shared host to one app.

## 5. Reload Prometheus and verify targets

Worth a quick `promtool check config prometheus/prometheus.yml` first (from
inside the `prometheus` container, or a local `promtool`) — with config now
split across many files, this catches a bad glob or YAML typo in your new
file before it silently fails to load.

```powershell
curl -X POST http://localhost:9090/-/reload
```

Check **Prometheus → Status → Targets** — the new job(s) should show `UP`.
If a brand-new app's jobs don't show up at all, double-check step 2's
`scrape_config_files` line was added and its glob matches your file's path.

## 6. Verify in Grafana

Open **Application Analytics**, switch the `job` dropdown to `my-app`.
Everything else resolves automatically:

- `$app` (hidden) derives from `$job` via the `app` label.
- `$db_job` (Layer 4) auto-populates with only this app's database job(s).
- Layer 2 panels auto-scope to this app's labeled host(s).
- `$route` (hidden) populates from this app's observed endpoints.

If a layer shows "No data," it usually means: the corresponding job/label
from steps 2-4 wasn't added, the `app` value doesn't match exactly across
jobs, or the target is down.

## 7. Optional: app-specific dashboard

**Currently disabled/paused** — `app-analytics.json` used to support linking
out to a per-app dashboard (see `core/authapi-analytics.json` for the
existing pattern: auth operations, dependency health, runtime internals),
via a `specific_dashboard` variable and an "App-Specific Dashboard Available"
panel. Both were removed from `app-analytics.json` while this feature is
redesigned — the mechanism and `authapi-analytics.json` itself are left
intact for when it comes back. Don't try to re-wire a new app into it until
this section is updated.

## 8. Optional: team-overview card

Each team has its own overview dashboard under
`grafana/provisioning/dashboards/<team-slug>/team-overview.json`
(e.g. `hr-finance/team-overview.json`, `public-safety/team-overview.json`).
Replace one of its "Placeholder App N" cards with this app: update its two
`up{job="..."}` targets and its link to
`/d/app-analytics?var-job=my-app&${__url_time_range}` (or
`/d/app-analytics-lite?...` per step 4's note). The Directors rollup
(`directors/all-teams-overview.json`) needs no changes — its per-team app
count is a live query against the `team:` label from step 1, not a
hand-maintained card.
