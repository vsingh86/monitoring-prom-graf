# ADO Backlog: Centralized Monitoring Platform (Pilot)

This backlog defines the build-out of a centralized Prometheus + Grafana
monitoring platform as a **pilot** — the goal is to prove the approach
(normalized cross-stack dashboards, a shared database-metrics collector,
zero-dashboard-edit app onboarding) with an initial small set of teams
and applications before proposing a wider rollout. Every item below is
written as work to be planned and built, not a record of what's already
been done — treat this as the backlog you'd load into ADO on day one of
the pilot.

Draft Epic/Feature/User Story breakdown, split into three parts:

- **Epic 1** — the platform build-out itself: core infrastructure,
  dashboards, documentation, and provisioning.
- **Epic 2** — the app-onboarding hand-off. A template Feature to clone
  per pilot application team.
- **Epic 3** — alerting (Alertmanager) and log aggregation (Loki),
  extending the pilot once the core metrics platform is proven out.

Each User Story includes a standard "As a / I want / so that," Acceptance
Criteria written as a checklist of things to build/configure/verify, and
a **Deliverable** reference — the file(s)/path(s) that story is expected
to produce, so implementers know exactly where their work lands in the
repo structure.

---

## Epic 1: Centralized Prometheus + Grafana Monitoring Platform

**Status:** To Do
**Pilot phase:** 1 — core platform
**Description:** Build a centralized, multi-tenant monitoring platform
that scrapes applications and their databases across multiple
teams/divisions, normalizes metrics across tech stacks and database
vendors into shared schemas, and provides a consistent set of Grafana
dashboards so onboarding a new application requires zero dashboard edits.
For the pilot, scope this to one team/division and a small number of
representative applications (covering at least two different tech
stacks and one database vendor) before considering wider rollout.

### Feature 1.1: Platform Core Infrastructure

**Status:** To Do

#### US 1.1.1 — Multi-team, multi-app Prometheus scrape architecture
As a platform engineer, I want scrape configs organized per team/app/environment
so that onboarding or changing one app can't accidentally break another
app's config, and adding a new environment for an existing app is a
zero-edit change.
**Acceptance Criteria:**
- [ ] Design and implement a `prometheus/scrape_configs/<team>/<app>/<env>.yml` directory layout — one file per app per environment.
- [ ] Keep the root `prometheus.yml` thin: global/alerting/`rule_files`/`scrape_config_files` only, no inline scrape jobs.
- [ ] Confirm and document Prometheus's glob restriction (`scrape_config_files`/`rule_files` only allow `*` in the final path segment) — each app gets one explicit line in `prometheus.yml`, not a directory-level wildcard.
**Deliverable:** `prometheus/prometheus.yml`, `prometheus/scrape_configs/`

#### US 1.1.2 — Recording-rule metric normalization across tech stacks
As a dashboard author, I want every tech stack's native metrics normalized
into shared `app:*`/`db:*`/`host:*` schemas so that the same dashboard
panel works unmodified across Node.js, .NET, .NET Framework, Java,
Postgres, MySQL, SQL Server, and Oracle.
**Acceptance Criteria:**
- [ ] Build `rules/data-mapping/{nodejs,dotnet,dotnet_framework,java}.yml` to normalize each stack's HTTP metrics to the shared `app:*` schema.
- [ ] Build `rules/data-mapping/db_{postgres,mysql,sqlserver,oracle}.yml` to normalize each vendor's DB metrics to the shared `db:*` schema.
- [ ] Build `rules/data-mapping/infra_{linux,windows}.yml` to normalize host metrics to the shared `host:*` schema.
- [ ] Every dashboard panel queries only the normalized schema — never a raw vendor metric name directly.
**Deliverable:** `prometheus/rules/data-mapping/`

#### US 1.1.3 — Unified database metrics collector (`db-exporter`)
As a platform engineer, I want one shared service to collect metrics from
all four supported database vendors so that I don't maintain four separate
per-vendor exporter deployments.
**Acceptance Criteria:**
- [ ] Build `db-exporter` to collect from Postgres/MySQL/SQL Server/Oracle via real SQL against each vendor's own stats views.
- [ ] Implement blackbox_exporter-style target selection (`?target=<name>` matching a `db-exporter/config.yaml` entry) so adding a database instance is a config change, not a code change.
- [ ] Write least-privilege monitoring-user SQL scripts (`db-exporter/sql/<vendor>_create_user.sql`) and matching grant-verification scripts (`<vendor>_verify_grants.sql`) per vendor.
- [ ] Document known limitations up front (e.g. no true per-call latency histogram on any vendor, Oracle deadlock counter is necessarily a proxy without licensed Diagnostics Pack features).
- [ ] Write unit tests against a mocked DB-API driver layer so the suite runs without a live database.
**Deliverable:** `db-exporter/`, `db-exporter/README.md`

#### US 1.1.4 — Standardized label conventions
As a dashboard author, I want a small set of required labels (`app`,
`team`, `app_type`, `db_type`, `host_type`, `component`, `environment`) so
that every dashboard can resolve which jobs belong to which application
without per-app dashboard customization.
**Acceptance Criteria:**
- [ ] Define the required label set and document it as mandatory on every scrape job.
- [ ] Design a `component` label (`app`/`frontend-app`/`backend-app`/`host`/`frontend-host`/`backend-host`/`database`) that lets a dashboard derive the right job for any role from `$app` alone, without guessing from job names.
- [ ] Require `team` to exactly match the destination Grafana folder's display name, since it drives a live per-team app count.
**Deliverable:** `CLAUDE.MD` "Key label conventions"

### Feature 1.2: Grafana Dashboard Suite

**Status:** To Do

#### US 1.2.1 — 2-tier Application Analytics dashboard family
As an app team, I want a generic analytics dashboard for single-job
applications (golden signals, infra, application detail, database) so
that I get full observability without anyone hand-building a dashboard for
my app.
**Acceptance Criteria:**
- [ ] Build `2-tier-fullstack-analytics` (app + host + db, full 4-layer dashboard).
- [ ] Build trimmed variants `2-tier-no-host-analytics` / `2-tier-no-db-analytics` / `2-tier-no-host-no-db-analytics` for apps missing one or both of host/db, so no dashboard shows a permanently-empty section.
- [ ] Scope all four entirely by a single `$app` variable; derive `$job`/`$host_job`/`$db_job` as hidden variables via the `component` label.
**Deliverable:** `grafana/provisioning/dashboards/core/2-tier-*.json`

#### US 1.2.2 — 3-tier Full-Stack Analytics dashboard family
As an app team with a genuine frontend/backend split, I want a dashboard
that shows both tiers plus their hosts and shared database side by side
so I don't have to flip between two single-job dashboards to see the
whole request path.
**Acceptance Criteria:**
- [ ] Build `3-tier-fullstack-analytics` — Frontend App, Frontend Host, Backend App, Backend Host, Database (5 layers).
- [ ] Build trimmed variants `3-tier-no-host-analytics` / `3-tier-no-db-analytics`.
- [ ] Scope entirely by `$app`; derive frontend/backend job and host variables via `component="frontend-app"`/`"backend-app"`/`"frontend-host"`/`"backend-host"`.
**Deliverable:** `grafana/provisioning/dashboards/core/3-tier-*.json`

#### US 1.2.3 — Team overview dashboards
As a team lead, I want one landing page per team showing every onboarded
app's status with a drill-in link to its full dashboard.
**Acceptance Criteria:**
- [ ] Build one `team-overview.json` per pilot team, provisioned into its own Grafana folder.
- [ ] Every app card links via `var-app=<AppName>` — a single consistent convention across both dashboard families.
**Deliverable:** `grafana/provisioning/dashboards/<team-slug>/team-overview.json`

#### US 1.2.4 — Directors rollup dashboard
As a director, I want a live count of onboarded applications per team so
I don't need a hand-maintained status spreadsheet.
**Acceptance Criteria:**
- [ ] Build `directors/all-teams-overview.json` to count distinct `app` label values per `team` label, live from Prometheus — not a hand-maintained card.
**Deliverable:** `grafana/provisioning/dashboards/directors/all-teams-overview.json`

#### US 1.2.5 — App-specific deep-dive dashboard (pilot showcase app)
As the pilot showcase app's team, I want an app-specific dashboard
covering domain-specific concerns (e.g. auth operations, dependency
health, runtime internals) in addition to the generic analytics
dashboard, to demonstrate the platform's extensibility beyond the generic
layer set.
**Acceptance Criteria:**
- [ ] Build one specialized dashboard for the pilot's showcase app, covering at least one domain-specific concern not in the generic dashboards.
- [ ] Link it back to the matching 2-tier/3-tier dashboard via `var-app=<AppName>`.
**Deliverable:** `grafana/provisioning/dashboards/core/<app>-analytics.json`

### Feature 1.3: Platform Documentation & Onboarding Process

**Status:** To Do

#### US 1.3.1 — Platform team onboarding checklist
As a platform engineer, I want a step-by-step checklist for wiring an
already-prepared app into Prometheus/Grafana so onboarding is repeatable
and doesn't depend on tribal knowledge.
**Acceptance Criteria:**
- [ ] Author a checklist covering label conventions, scrape job templates (app/db/host), the `component` split-vs-plain decision, Prometheus reload/verification, and team-overview card wiring.
**Deliverable:** `docs/onboarding-new-app.md`

#### US 1.3.2 — Consumer app team onboarding checklist
As an application team, I want a checklist of exactly what to prepare
before handing my app off to the platform team, so I don't go back and
forth discovering requirements one at a time.
**Acceptance Criteria:**
- [ ] Author a checklist covering exposing `/metrics` in the expected shape, installing a host exporter (or declaring vendor-hosted), requesting DBA grants, and the exact fields to hand back to the platform team.
**Deliverable:** `docs/onboarding-consumer-app.md`

#### US 1.3.3 — Architecture & conventions reference
As anyone joining this project, I want one authoritative document
describing the architecture, label conventions, directory layout, and
known gotchas, so I don't have to reverse-engineer them from code.
**Acceptance Criteria:**
- [ ] Author a reference document covering architecture, label conventions, directory layout, known gotchas, and current pilot state.
**Deliverable:** `CLAUDE.MD`

#### US 1.3.4 — DBA change-request template
As a platform engineer, I want a ready-to-use change-request draft for
requesting a new read-only database monitoring user, so requesting DBA
access for a new pilot app doesn't require reinventing the request from
scratch each time and doesn't risk requesting more access than needed.
**Acceptance Criteria:**
- [ ] Draft a ServiceHub-ready ticket template: purpose/context, exact grants requested per vendor, and what the account can/cannot do (read-only, no application data access).
- [ ] Include a per-vendor grant summary (Postgres/MySQL/SQL Server/Oracle) referencing the corresponding `db-exporter/sql/<vendor>_create_user.sql` script.
- [ ] Include a post-provisioning verification step using the matching `<vendor>_verify_grants.sql` script before the request is considered complete.
**Deliverable:** `docs/dba-request-template.md`

#### US 1.3.5 — Application metrics implementation guide
As an application team, I want a step-by-step instrumentation guide for
my specific tech stack, so I know exactly what metric names/labels to
emit instead of guessing and finding out only after my dashboard shows
"No data."
**Acceptance Criteria:**
- [ ] Author one section per supported `app_type` (Node.js, .NET/OpenTelemetry, .NET Framework, Java) with the exact metric names/labels the corresponding recording rule expects.
- [ ] Include a working setup/code sample per stack.
- [ ] Include a `curl`-and-verify step per stack so a team can self-check before requesting onboarding.
- [ ] Call out known instrumentation-library pitfalls to design around per stack (e.g. a library's default middleware emitting a metric shape that doesn't match the schema) as anticipated risks, so teams avoid them proactively rather than discovering them after deployment.
**Deliverable:** `docs/implementation-guide-app-metrics.md`

#### US 1.3.6 — Host metrics implementation guide
As a server/infrastructure team, I want step-by-step instructions for
installing and securely exposing host-level metrics on Linux and Windows
servers, so infrastructure-layer dashboards can be populated without the
platform team having to individually walk each server admin through it.
**Acceptance Criteria:**
- [ ] Author install instructions for `node_exporter` (Linux) and `windows_exporter` (Windows), including the exact collector set the corresponding recording rule requires.
- [ ] Cover securing the endpoint: firewall/security-group scoping to the Prometheus server, and an optional TLS + basic-auth setup for hosts reachable beyond a fully private network.
- [ ] Include a handoff checklist (host:port, OS type, auth method, shared-host caveat) for what to give back to the platform team.
**Deliverable:** `docs/implementation-guide-host-metrics.md`

### Feature 1.4: Infrastructure Provisioning (Docker Compose)

**Status:** To Do

#### US 1.4.1 — Containerized Prometheus + Grafana + db-exporter stack
As a platform engineer, I want the whole stack provisioned via a single
Docker Compose file so any team member can stand up the platform locally
or on a server with one command instead of manually configuring services.
**Acceptance Criteria:**
- [ ] Define `prometheus`, `grafana`, and `db-exporter` services in `docker-compose.yml` on a shared bridge network.
- [ ] Use named volumes so data persists across container restarts.
- [ ] Configure Prometheus with an appropriate retention window, a route prefix suited to how it'll be reverse-proxied, and live-reload support (`--web.enable-lifecycle`) so config changes don't require a full restart.
- [ ] Bind ports to localhost by default; document what changes if the pilot needs broader network access.
**Deliverable:** `docker-compose.yml`

#### US 1.4.2 — Secrets and per-app metrics tokens externalized via `.env`
As a platform engineer, I want required secrets (per-app bearer tokens,
Grafana admin password) sourced from an untracked `.env` file — with the
stack refusing to start rather than silently scraping nothing if one is
missing — so a misconfigured deployment fails loudly instead of shipping a
blank dashboard.
**Acceptance Criteria:**
- [ ] Prometheus container startup fails fast (non-zero exit, clear stderr message) if a required per-app metrics token is unset.
- [ ] Provide a committed `.env.example` documenting every variable the stack reads, with placeholder values only — the real `.env` stays gitignored.
- [ ] Design secret loading so a missing root `.env` only breaks the services that actually need it (e.g. `db-exporter`'s DB connections), not the whole Compose file's validation.
**Deliverable:** `docker-compose.yml`, `.env.example`

#### US 1.4.3 — Grafana datasource provisioning
As a platform engineer, I want Grafana's Prometheus datasource
auto-provisioned on startup so no one has to click through the UI to wire
it up by hand on a fresh deployment.
**Acceptance Criteria:**
- [ ] Auto-provision a Prometheus datasource pointed at the containerized Prometheus via `grafana/provisioning/datasources/`.
- [ ] Ensure exactly one file defines each datasource `uid` — design the provisioning directory so two files can't silently define conflicting datasources with the same uid (the same class of collision risk as dashboard uids, worth guarding against explicitly before Epic 3 adds a Loki datasource on top).
**Deliverable:** `grafana/provisioning/datasources/`

---

## Epic 2: Application Onboarding to Centralized Monitoring

**Status:** To Do
**Pilot phase:** 1 — core platform (runs in parallel with Epic 1 once the
platform can accept its first app)
**Description:** Template epic — clone Feature 2.1 once per pilot
application team. Each application team is responsible for the
prerequisites in Feature 2.1; the platform team then wires the app in per
the checklist built under Epic 1 (US 1.3.1) — no new platform work
expected unless the app needs a new `app_type`/`db_type` mapping.

### Feature 2.1: Onboard `<Application Name>` to Centralized Monitoring

*(Duplicate this Feature per pilot app; replace `<Application Name>` and
fill in the app's actual stack/hosting details.)*

**Status:** To Do
**Owning team:** `<consuming application team>`
**Description:** Complete the prerequisites defined in Epic 1 (US 1.3.2,
US 1.3.5, US 1.3.6) and hand the results to the platform team.

#### US 2.1.1 — Expose a Prometheus-format `/metrics` endpoint
As the `<App>` team, I want my application to expose a `/metrics` endpoint
in the exact shape the platform's recording rules expect, so my dashboard
shows real data instead of silently showing "No data."
**Acceptance Criteria:**
- [ ] `/metrics` endpoint reachable over HTTP, using the library matching our `app_type` (`prom-client` for Node.js, `OpenTelemetry.Instrumentation.AspNetCore` for modern .NET, `prometheus-net` for .NET Framework, Micrometer for Java) per the implementation guide (US 1.3.5).
- [ ] Ran `curl http://our-app:port/metrics` and confirmed metric names/labels match the recording rule for our `app_type` — **do this before handoff**, not after the dashboard shows nothing.
- [ ] Any mismatch flagged to the platform team before handoff, not discovered after.
**Deliverable:** App-side instrumentation change (outside this repo)

#### US 2.1.2 — Install a host exporter, or confirm vendor-hosted
As the `<App>` team, I want host-level metrics (CPU/memory/disk/network)
available if we control the infrastructure, or to explicitly flag that we
don't, so the platform team wires the correct dashboard variant.
**Acceptance Criteria:**
- [ ] If self-hosted: `node_exporter` (Linux) or `windows_exporter` (Windows) installed per the host metrics implementation guide (US 1.3.6) and reachable.
- [ ] If vendor-hosted/no reachable infra: explicitly confirmed to the platform team (drives the `no-host` dashboard variant choice).
**Deliverable:** Host-side exporter installation (outside this repo)

#### US 2.1.3 — Request DBA-provisioned read-only monitoring user
As the `<App>` team, I want our database exposed to the shared
`db-exporter` service via a dedicated least-privilege monitoring user
(never application credentials), so DB metrics show up without expanding
our app's DB credential's blast radius.
**Acceptance Criteria:**
- [ ] Submitted the DBA change request (US 1.3.4 template) matching our database vendor.
- [ ] Grants verified via the matching `*_verify_grants.sql` script logged in as the new monitoring user — every query succeeds.
- [ ] If no database, or vendor-managed with no DBA access: explicitly confirmed to the platform team (drives the `no-db` dashboard variant choice).
**Deliverable:** DBA-provisioned account (outside this repo)

#### US 2.1.4 — Hand off app details to the platform team
As the `<App>` team, I want to give the platform team everything they need
in one pass, so onboarding doesn't take multiple round trips.
**Acceptance Criteria:**
- [ ] App name (PascalCase, for the `app` label) provided.
- [ ] Team name (exact Grafana folder display name, for the `team` label) provided.
- [ ] Metrics endpoint (host:port, path, auth method) provided.
- [ ] `app_type` provided.
- [ ] Host exporter address, or vendor-hosted confirmation, provided.
- [ ] Database connection details (host, port, db name, monitoring username, password location — a secret, not chat/email), if applicable, provided.
- [ ] Environment(s) (dev/staging/production) provided.
**Deliverable:** Handoff record (ADO comment/attachment, or equivalent)

#### US 2.1.5 — Verify the dashboard together with the platform team
As the `<App>` team, I want to confirm our dashboard actually shows real
data before calling onboarding done, so a silent metric-shape mismatch
doesn't sit undiscovered.
**Acceptance Criteria:**
- [ ] Prometheus **Targets** page shows our job(s) as `UP`.
- [ ] Grafana dashboard (matching 2-tier or 3-tier variant, selected via `$app`) shows real data on every layer we expect populated.
- [ ] Any "No data" layer investigated and resolved (missing label, `component` mismatch, or target down) before sign-off.
**Deliverable:** Joint sign-off (ADO/ServiceHub record)

---

## Epic 3: Alerting & Log Aggregation (Alertmanager + Loki)

**Status:** To Do
**Pilot phase:** 2 — extends the pilot once core metrics/dashboards
(Epic 1) are validated with real onboarded apps (Epic 2)
**Description:** Extend the pilot platform with centralized alert routing
and log aggregation, so the pilot can demonstrate the full
metrics-plus-alerting-plus-logs observability story before a wider
rollout decision is made.

### Feature 3.1: Alertmanager — Centralized Alert Routing

**Status:** To Do

#### US 3.1.1 — Deploy Alertmanager
As a platform engineer, I want Alertmanager deployed and receiving fired
alerts from Prometheus so the pilot can demonstrate automated alert
routing, not just dashboards someone has to actively watch.
**Acceptance Criteria:**
- [ ] Add an `alertmanager` service to `docker-compose.yml`.
- [ ] Design `alertmanager.yml`'s routing: group related alerts sensibly (e.g. by alert name, component, and app), set appropriate group-wait/repeat-interval values, and inhibit lower-severity duplicate alerts when a higher-severity one for the same issue is already firing.
- [ ] Wire Prometheus's `alerting.alertmanagers` target at Alertmanager's address in `prometheus.yml`; confirm connectivity in the Prometheus UI.
**Deliverable:** `docker-compose.yml`, `prometheus/alertmanager.yml`, `prometheus/prometheus.yml`

#### US 3.1.2 — Build the alert notification relay
As a platform engineer, I want fired alerts forwarded to wherever the
pilot's on-call notification target lives (e.g. an AWS Lambda function
fanning out to Slack/Teams/PagerDuty), so alerts actually reach a human
instead of sitting in Alertmanager's UI.
**Acceptance Criteria:**
- [ ] Decide and document the notification target (Lambda Function URL, or an alternative) and the auth mechanism between Alertmanager and it.
- [ ] Build a relay service that receives Alertmanager's webhook POST, applies whatever auth/header transformation the target requires, and forwards it.
- [ ] Add the relay as a `docker-compose.yml` service; wire Alertmanager's receiver to call it.
- [ ] End-to-end test: a manually-fired test alert flows Prometheus → Alertmanager → relay → notification target successfully.
- [ ] Source all credentials from `.env`; never commit them.
**Deliverable:** new relay service directory, `docker-compose.yml`, `.env.example`

#### US 3.1.3 — Alert rule coverage for pilot apps
As a platform engineer, I want every pilot-onboarded app to have basic
alert rules, so a production-like incident during the pilot doesn't go
unnoticed simply because no one wrote rules for that app yet.
**Acceptance Criteria:**
- [ ] Write alert rules for each pilot app, covering at minimum error-rate and latency thresholds consistent with the Warn/Critical thresholds already used in that app's dashboard panels, so alerts and dashboards agree.
- [ ] Wire each app's alert-rule directory into `prometheus.yml`'s `rule_files` (one explicit line per directory, same glob restriction as scrape configs).
**Deliverable:** `prometheus/rules/alerts/<app>/*.yml`, `prometheus/prometheus.yml`

#### US 3.1.4 — Document alerting conventions for consuming teams
As an application team, I want to know how to get alerts wired up for my
app and what determines how my alerts get grouped/routed, so I'm not
guessing at conventions the platform team decided.
**Acceptance Criteria:**
- [ ] Extend the onboarding docs (US 1.3.1/US 1.3.2) with a section on alert rules: how to request them, and how the grouping labels affect notification behavior.
- [ ] Extend `CLAUDE.MD`'s label conventions to note that `component`/`app` also drive alert grouping, not just dashboards.
**Deliverable:** `docs/onboarding-new-app.md`, `docs/onboarding-consumer-app.md`, `CLAUDE.MD`

### Feature 3.2: Loki — Centralized Log Aggregation

**Status:** To Do

#### US 3.2.1 — Deploy Loki
As a platform engineer, I want a log aggregation backend running so the
pilot can demonstrate logs alongside metrics in the same tool, rather
than each app team maintaining separate log tooling.
**Acceptance Criteria:**
- [ ] Write a Loki configuration file suited to the pilot's expected log volume/retention needs.
- [ ] Add a `loki` service to `docker-compose.yml` with a persistent volume.
- [ ] Wire Grafana to depend on Loki being available.
- [ ] Confirm Loki is reachable and its data persists across container restarts.
**Deliverable:** `loki/loki-config.yml`, `docker-compose.yml`

#### US 3.2.2 — Provision the Grafana Loki datasource
As a platform engineer, I want Grafana able to query Loki once it's live,
using a clean, non-conflicting datasource definition.
**Acceptance Criteria:**
- [ ] Confirm US 1.4.3's "exactly one definition per datasource uid" requirement holds before adding Loki, so this doesn't inherit a provisioning conflict.
- [ ] Provision a Loki datasource and confirm it works (**Grafana → Explore**, select Loki, run a basic query) once the Loki container is running.
**Deliverable:** `grafana/provisioning/datasources/`

#### US 3.2.3 — Choose and deploy a log shipping agent
As a platform engineer, I want container/host logs actually flowing into
Loki — a log backend with nothing shipping to it demonstrates nothing.
**Acceptance Criteria:**
- [ ] Evaluate and choose a log-shipping approach (e.g. Promtail, Grafana Alloy, or Docker's native Loki logging driver) and document the decision and rationale.
- [ ] Ship logs from at minimum the platform's own containers (Prometheus, Grafana, db-exporter) into Loki as a proof of concept.
**Deliverable:** new log-shipping configuration (path TBD by chosen approach)

#### US 3.2.4 — Define log label conventions consistent with existing metric labels
As a dashboard user, I want to pivot from a metrics panel straight into
the matching logs, so I want logs tagged with the same `app`/`team`/
`environment` values already used throughout Prometheus.
**Acceptance Criteria:**
- [ ] Design log labels to reuse the exact `app`/`team`/`environment` values already established for metrics, so logs and metrics for the same app correlate directly.
- [ ] Document the convention in `CLAUDE.MD` alongside the existing metric label conventions.
**Deliverable:** `CLAUDE.MD` (extended), log-shipping configuration

#### US 3.2.5 — Add a Logs row to the dashboard family (stretch)
As an app team, I want to jump from a spike on a Golden Signals panel
straight into the logs for that same time window and app, without
switching dashboards.
**Acceptance Criteria:**
- [ ] Explicitly a stretch goal — does not block the rest of Feature 3.2.
- [ ] If picked up: add a collapsed "Logs" row to the 2-tier/3-tier dashboard families, scoped by `$app` (and `$frontend_job`/`$backend_job` for the 3-tier family), consistent with the existing per-layer row pattern.
**Deliverable:** `grafana/provisioning/dashboards/core/*.json`
