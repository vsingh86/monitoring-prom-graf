# Centralized Monitoring

Prometheus + Grafana stack for monitoring real applications and infrastructure.

## Layout

```
.
├── docker-compose.yml
├── .env.example                          # db-exporter DB passwords -- copy to .env at repo root
├── prometheus/
│   ├── prometheus.yml                    # scrape configs + rule_files references
│   └── recording_rules/                  # native metrics -> app:*/db:*/host:* schema, per stack
├── db-exporter/                          # multi-database Prometheus exporter (see its README)
├── docs/
│   └── onboarding-new-app.md             # full checklist for adding a new app
└── grafana/
    ├── provisioning/
    │   ├── datasources/                  # Prometheus datasource (auto-provisioned)
    │   └── dashboards/                   # dashboard provider config
    └── dashboards/
        ├── app-analytics.json            # generic per-app analytics dashboard
        ├── authapi-analytics.json        # AuthApi-specific deep dive
        ├── frontend-analytics.json       # frontend RUM dashboard
        └── team-overview.json            # landing page linking to the above
```

## Run it

```powershell
docker compose up -d
```

- Prometheus: http://localhost:9090 (check **Status > Targets**)
- Grafana: http://localhost:3000 (login: `admin` / `admin`)

This starts prometheus/grafana/node-exporter even with no setup. `db-exporter`
(database metrics) needs its own config first — see
[`db-exporter/README.md`](db-exporter/README.md); its passwords come from a
repo-root `.env` (copy from `.env.example`), which is optional for everything
else in this stack.

> Note: if `monitoring-prom-graf` is still running, stop it first (`docker compose down` in that directory) — both stacks use ports 9090/3000/9100.

> **`docker compose down` tears down the whole project, not one service.**
> To stop/remove just one container (e.g. while testing `db-exporter`), use
> `docker compose stop <service>` / `docker compose rm -f <service>` instead —
> `down` will also stop unrelated containers you didn't start this session.

## What's scraped

| Job            | Target                                  | Notes                                  |
|----------------|------------------------------------------|----------------------------------------|
| `prometheus`   | self                                       | Prometheus' own metrics                 |
| `node-exporter`| `node-exporter:9100`                      | Host CPU/memory/disk/network            |
| `authapi`      | `api.hris-stage.adc.seattle.gov` (https)  | Real app — AuthApi staging              |
| `authapi-postgres` / `myapp-mysql` / `myapp-sqlserver` / `myapp-oracle` | `db-exporter:9433` (`params.target=<name>`) | Database metrics, via the shared [`db-exporter`](db-exporter/README.md) service |

## Dashboard

`Application Analytics` (`app-analytics`) is templated on a `job` variable
(defaults to `authapi`). It covers:

- **Layer 1 — Golden Signals**: latency (p50/p95/p99), traffic, errors, saturation
- **Layer 2 — Infrastructure**: CPU, memory, swap, disk I/O, disk space, network (from `node-exporter`)
- **Layer 3 — Application**: request rate by endpoint, error breakdown, business transactions, external dependency latency
- **Layer 4 — Database**: query latency, connection saturation, replication lag, locks, DB size
- **Drilldowns**: slowest endpoints, highest-error endpoints, per-operation detail

Panels that need metrics this app doesn't expose (e.g. Postgres, business
transaction counters) will simply show "No data" until that instrumentation
is added.

## Multi-stack support — how it works

`app-analytics.json` queries a normalized `app:*` metric schema so the same
dashboard works across Node.js, .NET, and Java apps without modification.
Prometheus recording rules in `prometheus/recording_rules/` do the translation:

| Tech stack | Native metric (inbound) | Native labels | Normalized to |
|---|---|---|---|
| Node.js (prom-client) | `http_requests_total` | `route`, `status_code` | `app:http_requests_total` |
| Node.js (prom-client) | `http_request_duration_seconds` | `route`, `status_code` | `app:http_request_duration_seconds_*` |
| .NET (OTel ASP.NET Core) | `http_server_request_duration_seconds` | `http_route`, `http_response_status_code` | `app:http_request_duration_seconds_*` |
| .NET Framework (prometheus-net) | `http_requests_total` / `http_request_duration_seconds` | `endpoint` (or `page` for UI components) | `app:http_requests_total` / `app:http_request_duration_seconds_*` |
| Java (Micrometer/Spring Boot) | `http_server_requests_seconds` | `uri`, `status` | `app:http_request_duration_seconds_*` |

Rules are scoped by an `app_type` label (`nodejs` / `dotnet` / `dotnet-framework` /
`java`) set as a static label on each scrape job — so adding a new app of an
existing stack requires **only a scrape job entry**; no rule files or dashboard
changes needed.

> **`dotnet` vs `dotnet-framework`:** these are two distinct stacks with
> incompatible native metric names, not two names for the same thing. `dotnet`
> assumes modern .NET + OpenTelemetry ASP.NET Core auto-instrumentation.
> `dotnet-framework` assumes classic .NET Framework (pre-.NET-Core) manually
> instrumented with the `prometheus-net` library — see
> `prometheus/recording_rules/dotnet_framework.yml` for the exact metric
> mapping (derived from real scrape samples in `sample-scrape-files/`).

## Adding another real app

See [`docs/onboarding-new-app.md`](docs/onboarding-new-app.md) for the full
checklist — application job, optional database/infra jobs, the shared `app`
label convention that ties them together, and dashboard verification steps.

## Stopping

```powershell
docker compose down          # stop containers, keep data
docker compose down -v       # stop containers and delete data
```
