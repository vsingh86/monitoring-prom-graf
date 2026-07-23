# Onboarding a new app

Checklist for adding a new application to this monitoring stack so it shows
up correctly in `Application Analytics` (`app-analytics.json`) — Layer 1
(Golden Signals), Layer 2 (Infrastructure), Layer 3 (Application), and
Layer 4 (Database) — with no dashboard edits required.

## 1. Pick an `app` label value

Choose a unique name (e.g. `AuthApi`, PascalCase to match existing convention).
**Every job that belongs to this app — its application job, database job(s),
and infra host job(s) — must set `app: <Name>` with this exact value.**

This is the join key `app-analytics.json` uses internally to tie an
application's request metrics, database metrics, and host metrics together.
Skipping it, or using a different value on one of the jobs, means that
job's data won't show up when you select this app in the dashboard.

## 2. Add the application scrape job (required)

In `prometheus/prometheus.yml`, under `# ── Real Applications ──`:

```yaml
- job_name: my-app
  metrics_path: /metrics          # wherever the app exposes Prometheus metrics
  static_configs:
    - targets: ["my-app-host:port"]
      labels:
        app: MyApp
        app_type: nodejs           # or: dotnet, dotnet-framework, java
        environment: production
```

`app_type` must match one of the existing `prometheus/recording_rules/<stack>.yml`
files (`nodejs`, `dotnet`, `dotnet-framework`, `java`), which normalize that
stack's native HTTP metrics into the shared `app:*` schema the dashboard
queries. If your stack isn't one of these, add a new `recording_rules/<stack>.yml`
following the same pattern (filter on `app_type="<stack>"`, map native
metric/label names to `app:*`) and reference it under `rule_files:` in
`prometheus.yml`.

> Note: `dotnet` (modern .NET + OpenTelemetry ASP.NET Core) and
> `dotnet-framework` (classic .NET Framework + `prometheus-net`) are separate
> `app_type` values because their native metric names are incompatible — pick
> based on how the app is actually instrumented, not just its language.

## 3. Add database job(s) — optional, only if Layer 4 applies

All four database types are served by one shared service,
[`db-exporter`](../db-exporter/README.md) — Prometheus doesn't scrape the
database directly, it scrapes `db-exporter` with a `params.target` selecting
which configured database to query (blackbox_exporter-style):

```yaml
- job_name: my-app-postgres
  params:
    target: ["my-app-postgres"]   # must match a "name:" entry in db-exporter/config.yaml
  static_configs:
    - targets: ["db-exporter:9433"]
      labels:
        app: MyApp                # same value as step 1
        db_type: postgres         # or: mysql, sqlserver, oracle
        environment: production
  relabel_configs:
    - source_labels: [__param_target]
      target_label: instance
```

You also need to add the actual connection details to
`db-exporter/config.yaml` (and its password to the repo-root `.env`) — see
[`db-exporter/README.md`](../db-exporter/README.md#adding-a-database) for
the full steps. `db_type` must match an existing `recording_rules/db_<type>.yml`
(`postgres`, `mysql`, `sqlserver`, `oracle`), or a new one following the same
pattern (plus a new `db-exporter/src/collectors/<type>.py`).

## 4. Add infra host job(s) — optional, only if Layer 2 should scope to this app

One exporter job per host:

```yaml
- job_name: windows-exporter-my-app-host
  static_configs:
    - targets: ["my-app-host.example.com:9182"]
      labels:
        app: MyApp                # same value as step 1
        host_type: windows        # or: linux (node-exporter)
        environment: production
```

If a host is shared across multiple apps, leave `app` off entirely — the
dashboard will correctly show no infra data for it under any single app's
view rather than attributing a shared host to one app.

## 5. Reload Prometheus and verify targets

```powershell
curl -X POST http://localhost:9090/-/reload
```

Check **Prometheus → Status → Targets** — the new job(s) should show `UP`.

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

If this app needs extra panels beyond the generic layers (see
`authapi-analytics.json` for the pattern — auth operations, dependency
health, runtime internals), create a new dashboard file and add it to the
`specific_dashboard` custom variable's options in `app-analytics.json`. It
will then surface as a linked panel ("App-Specific Dashboard Available")
when this app is selected.

## 8. Optional: team-overview card

Replace one of the "Placeholder App N" cards in `team-overview.json` with
this app: update its two `up{job="..."}` targets and its link to
`/d/app-analytics?var-job=my-app` (add `&var-specific_dashboard=<uid>` if
step 7 applies).
