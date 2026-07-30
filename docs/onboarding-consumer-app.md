# Onboarding your app: a guide for consuming teams

This doc is for **your team** — the team that owns the application being
monitored — not the platform team. It covers what you need to prepare and
hand off before your app shows up in Grafana. Once you've done the steps
here, hand the results to the platform team, who follow
[`onboarding-new-app.md`](onboarding-new-app.md) to actually wire your app
into Prometheus/Grafana. That doc assumes everything below is already done;
this doc is what makes that true.

## 1. Expose a `/metrics` endpoint

Your app needs to serve Prometheus-format metrics over HTTP. Which library
to use depends on your stack — pick the one matching your `app_type`:

| `app_type` | Stack | Library |
|---|---|---|
| `nodejs` | Node.js | [`prom-client`](https://github.com/siimon/prom-client) |
| `dotnet` | Modern .NET / ASP.NET Core, OpenTelemetry-instrumented | `OpenTelemetry.Instrumentation.AspNetCore` |
| `dotnet-framework` | Classic .NET Framework (pre-.NET-Core) | [`prometheus-net`](https://github.com/prometheus-net/prometheus-net) |
| `java` | Java/JVM | [Micrometer](https://micrometer.io/) with the Prometheus registry |

### This is the step most likely to go wrong — match the exact metric shape

The platform team's recording rules (`prometheus/rules/data-mapping/<stack>.yml`)
normalize each stack's *specific* metric names and labels into the shared
`app:*` schema every dashboard queries. If your instrumentation doesn't
match what the rule for your `app_type` expects, Prometheus will scrape your
app fine — `up{job="..."}` will show `1` — but every dashboard panel will
silently show "No data," because the recording rule that's supposed to
normalize your metrics never matches anything.

**This happened twice on this platform already**, both times because an app
used a library's *default* metric names instead of what the recording rule
expected:
- One `dotnet-framework` app used `prometheus-net.AspNetCore`'s stock
  `UseHttpMetrics()` middleware, which emits `http_requests_received_total`
  with a `code` label — the recording rule was written for a hand-rolled
  `http_requests_total` counter with a `status_code` label. Same library,
  different configuration, incompatible metric names.
- A SQL Server target initially had no scrape job at all pointed at it, so
  it silently produced zero data despite the exporter itself working fine.

**Before you ask the platform team to add your app, open the recording rule
file for your exact `app_type`** and confirm your app's real scrape output
(`curl http://your-app:port/metrics`) matches what it expects:
- [`rules/data-mapping/nodejs.yml`](../prometheus/rules/data-mapping/nodejs.yml)
- [`rules/data-mapping/dotnet.yml`](../prometheus/rules/data-mapping/dotnet.yml)
- [`rules/data-mapping/dotnet_framework.yml`](../prometheus/rules/data-mapping/dotnet_framework.yml)
- [`rules/data-mapping/java.yml`](../prometheus/rules/data-mapping/java.yml)

If your output doesn't match, either reconfigure your instrumentation to
produce the expected names/labels, or flag it to the platform team — they
can extend the recording rule to recognize your shape too (as happened for
the `prometheus-net` default-middleware case above), but that's much faster
to do *before* onboarding than after a dashboard silently shows nothing.

## 2. Self-hosted only: install a host exporter (Layer 2)

If your app runs on infrastructure your team controls (a VM, an on-prem
server), install the matching exporter so host-level metrics (CPU, memory,
disk, network) show up on Layer 2:
- Linux: [`node_exporter`](https://github.com/prometheus/node_exporter)
- Windows: [`windows_exporter`](https://github.com/prometheus-community/windows_exporter)

**If your app runs on vendor-hosted/managed infrastructure you can't reach**
(can't install an exporter, can't scrape the host), skip this — say so
explicitly when you hand off to the platform team. Your app will use the
`app-analytics-lite` dashboard variant instead of the full one, which
doesn't have a permanently-empty Infrastructure section.

## 3. If you have a database: request DBA grants

Databases are scraped through a shared service (`db-exporter`), not
per-vendor exporters, and it connects as a dedicated **read-only monitoring
user** — never with application credentials. Give your DBA the setup script
matching your database type:
- [`db-exporter/sql/postgres_create_user.sql`](../db-exporter/sql/postgres_create_user.sql)
- [`db-exporter/sql/mysql_create_user.sql`](../db-exporter/sql/mysql_create_user.sql)
- [`db-exporter/sql/sqlserver_create_user.sql`](../db-exporter/sql/sqlserver_create_user.sql)
- [`db-exporter/sql/oracle_create_user.sql`](../db-exporter/sql/oracle_create_user.sql)

Each script only grants what's actually needed to read query stats,
connection counts, locks, and size — nothing that touches your data. After
the DBA runs it, verify the grants actually work (catches a missing
permission before it becomes a silent gap in the dashboard) with the
matching `*_verify_grants.sql` script in the same directory — run it logged
in as the new monitoring user, every query in it should succeed.

If you don't have a database, or it's fully managed by a vendor you have no
DBA access to, say so — same as step 2, that's a `app-analytics-lite`
situation for Layer 4.

## 4. What to hand back to the platform team

Once the steps above are done, hand the platform team (who'll follow
[`onboarding-new-app.md`](onboarding-new-app.md)):

- **App name** — the value you want for the `app` label (PascalCase, e.g. `MyApp`).
- **Team name** — which team folder this belongs under (e.g. `HR and Finance`,
  `Public Safety`, `Middleware`) — becomes the `team` label.
- **Metrics endpoint** — host:port, path (if not `/metrics`), and how it's
  authenticated (bearer token, basic auth, none).
- **`app_type`** — which stack/instrumentation you used (step 1's table).
- **Host exporter address**, if self-hosted (step 2) — or confirmation
  you're vendor-hosted and need the lite dashboard.
- **Database connection details**, if applicable (step 3) — host, port,
  database name, the monitoring username, and where its password will live
  (a secret, not in chat/email).
- **Environment(s)** — dev/staging/production, whichever apply.

## 5. Next step

Once the platform team has everything above, they take it from here via
[`onboarding-new-app.md`](onboarding-new-app.md) — adding the Prometheus
scrape job(s), reloading Prometheus, and verifying the dashboard. You
shouldn't need to touch anything in this repo yourself.
