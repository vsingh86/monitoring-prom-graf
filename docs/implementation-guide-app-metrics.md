# Implementation guide: exposing application metrics

Step-by-step instrumentation guide for application teams, one section per
stack. This is the detailed how-to behind
[`onboarding-consumer-app.md`](onboarding-consumer-app.md) step 1 — read
that doc first for the overall handoff process; this doc is what you
actually implement.

**Why the exact shape matters:** the platform's recording rules
(`prometheus/rules/data-mapping/<stack>.yml`) normalize each stack's
*specific* metric names and labels into a shared `app:*` schema every
dashboard queries. Prometheus will happily scrape your app and show
`up{job="..."}=1` even if your metric names don't match — the failure is
silent. The dashboard just shows "No data," because the recording rule
that's supposed to normalize your metrics never matched anything. **This
has already happened twice on this platform** (see the `dotnet-framework`
and Java sections below for the specific traps) — verify your actual
scrape output against the tables below *before* asking the platform team
to onboard your app, not after.

Jump to your stack: [Node.js](#nodejs) · [.NET (modern / OTel)](#net-modern--opentelemetry) · [.NET Framework](#net-framework) · [Java](#java-spring-boot--micrometer)

---

## Node.js

**Library:** [`prom-client`](https://github.com/siimon/prom-client)
**`app_type` label:** `nodejs`
**Recording rule:** [`prometheus/rules/data-mapping/nodejs.yml`](../prometheus/rules/data-mapping/nodejs.yml)

`prom-client`'s metrics pass through to the `app:*` schema unchanged — no
label renaming needed, which makes this the simplest stack to match.

### Required metrics and labels

| Your metric must be named | Type | Required labels |
|---|---|---|
| `http_requests_total` | Counter | `status_code` |
| `http_request_duration_seconds` | Histogram | (route label recommended, see below) |

Optional but recommended for outbound-call panels:
| `http_client_request_duration_seconds` | Histogram | for calls *your app makes* to other services |

### Setup

```js
const client = require('prom-client');
const register = new client.Registry();
client.collectDefaultMetrics({ register });

const httpRequestsTotal = new client.Counter({
  name: 'http_requests_total',
  help: 'Total HTTP requests',
  labelNames: ['method', 'route', 'status_code'],
  registers: [register],
});

const httpRequestDuration = new client.Histogram({
  name: 'http_request_duration_seconds',
  help: 'HTTP request duration in seconds',
  labelNames: ['method', 'route', 'status_code'],
  buckets: [0.01, 0.05, 0.1, 0.3, 0.5, 1, 3, 5],
  registers: [register],
});

// Express middleware — record on every request
app.use((req, res, next) => {
  const end = httpRequestDuration.startTimer();
  res.on('finish', () => {
    const route = req.route?.path || req.path; // use the route TEMPLATE, not the raw URL
    const labels = { method: req.method, route, status_code: res.statusCode };
    httpRequestsTotal.inc(labels);
    end(labels);
  });
  next();
});

app.get('/metrics', async (req, res) => {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
});
```

**Important — use the route *template*, not the raw URL.** `req.route.path`
gives you `/api/orders/:id`, not `/api/orders/12345`. Using the raw URL as
a label value creates unbounded label cardinality (one series per unique
order ID ever requested) and will eventually cause Prometheus memory
problems. This applies to every stack below too.

### Verify before handoff

```bash
curl http://localhost:PORT/metrics | grep -E '^http_requests_total|^http_request_duration_seconds'
```
Confirm `status_code` actually appears as a label on the output lines, not
just in your code.

---

## .NET (modern / OpenTelemetry)

**Library:** `OpenTelemetry.Instrumentation.AspNetCore` +
`OpenTelemetry.Exporter.Prometheus.AspNetCore`
**`app_type` label:** `dotnet` (not `dotnet-framework` — see below)
**Recording rule:** [`prometheus/rules/data-mapping/dotnet.yml`](../prometheus/rules/data-mapping/dotnet.yml)

This is for **modern .NET / ASP.NET Core** apps using OpenTelemetry
auto-instrumentation. If your app is classic .NET Framework (pre-.NET
Core), skip to the [.NET Framework](#net-framework) section instead — the
native metric shapes are completely different and `app_type` must match
which one you actually used.

### What the recording rule expects

OTel's ASP.NET Core auto-instrumentation emits
`http_server_request_duration_seconds` (a histogram) with labels
`http_route`, `http_request_method`, `http_response_status_code`. The
recording rule `label_replace`s these into the schema's `route`/
`status_code` names — **you don't rename anything yourself**, just make
sure the auto-instrumentation is actually wired up and `app_type: dotnet`
is set on your scrape job (the platform team sets this, but tell them
`dotnet` specifically, not `dotnet-framework`).

### Setup

```csharp
// Program.cs
using OpenTelemetry.Metrics;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenTelemetry()
    .WithMetrics(metrics => metrics
        .AddAspNetCoreInstrumentation()   // emits http_server_request_duration_seconds
        .AddHttpClientInstrumentation()   // emits http_client_request_duration_seconds (outbound calls)
        .AddPrometheusExporter());

var app = builder.Build();

app.MapPrometheusScrapingEndpoint();      // exposes /metrics by default

app.Run();
```

No manual counters needed — `AddAspNetCoreInstrumentation()` handles
every inbound request automatically with the exact labels the recording
rule expects.

### Verify before handoff

```powershell
curl http://localhost:PORT/metrics | Select-String "http_server_request_duration_seconds"
```
Confirm the output includes `http_route=`, `http_request_method=`, and
`http_response_status_code=` labels.

---

## .NET Framework

**Library:** [`prometheus-net`](https://github.com/prometheus-net/prometheus-net)
(NOT `prometheus-net.AspNetCore`'s auto-instrumentation — see the warning
below)
**`app_type` label:** `dotnet-framework`
**Recording rule:** [`prometheus/rules/data-mapping/dotnet_framework.yml`](../prometheus/rules/data-mapping/dotnet_framework.yml)

This is for **classic .NET Framework** (pre-.NET Core) apps, which can't
use OpenTelemetry's ASP.NET Core auto-instrumentation. This stack's
recording rule assumes **manual instrumentation**, confirmed against real
scrape output from a production app on this platform.

###
**Emit a manually-named counter, don't rely on default middleware
output:**

### Required metrics and labels

| Your metric must be named | Type | Required labels |
|---|---|---|
| `http_requests_total` | Counter | `endpoint`, `status_code` |
| `http_request_duration_seconds` | Histogram | `endpoint` |

(The recording rule maps `endpoint` → the schema's `route` label — name
your label `endpoint`, not `route`.)

### Setup (OWIN / `prometheus-net`)

```csharp
// Global.asax.cs or OWIN Startup.cs
using Prometheus;

var requestsTotal = Metrics.CreateCounter(
    "http_requests_total", "Total HTTP requests",
    new CounterConfiguration { LabelNames = new[] { "endpoint", "status_code" } });

var requestDuration = Metrics.CreateHistogram(
    "http_request_duration_seconds", "HTTP request duration in seconds",
    new HistogramConfiguration {
        LabelNames = new[] { "endpoint" },
        Buckets = Histogram.LinearBuckets(start: 0.01, width: 0.1, count: 10)
    });

// In your action filter / HttpModule, on every request completion:
var endpointTemplate = GetRouteTemplate(request); // e.g. "/api/orders/{id}", not the raw URL
using (requestDuration.WithLabels(endpointTemplate).NewTimer())
{
    // ... handle request ...
}
requestsTotal.WithLabels(endpointTemplate, ((int)response.StatusCode).ToString()).Inc();

// Expose /metrics
app.UseMetricServer(); // or wire MetricServer.Start() for a self-hosted endpoint
```

If your app has a **separate UI component with no per-route breakdown**
(a single aggregate page-load counter, no status/route labels at all),
the recording rule also recognizes `ui_requests_total` (a bare counter)
and `ui_page_load_seconds_{bucket,count,sum}{page}` — but be aware panels
that filter/group by `status_code` or `route` (2xx RPS, Error Count by
Status Code, Request Rate by Endpoint) will show "No data" for that
component, since a bare aggregate counter has nothing to filter by. This
is a real limitation of that shape, not something the platform side can
fix — if you need those panels populated, emit the labeled
`http_requests_total`/`http_request_duration_seconds` shape above
instead, even for UI-served pages.

### Verify before handoff

```powershell
curl http://localhost:PORT/metrics | Select-String "^http_requests_total"
```
Confirm the metric name is exactly `http_requests_total` (not
`http_requests_received_total`) and `status_code` (not `code`) appears as
a label.

---

## Java (Spring Boot + Micrometer)

**Library:** [Micrometer](https://micrometer.io/) with the Prometheus
registry (`micrometer-registry-prometheus`) + Spring Boot Actuator
**`app_type` label:** `java`
**Recording rule:** [`prometheus/rules/data-mapping/java.yml`](../prometheus/rules/data-mapping/java.yml)

### What the recording rule expects

Micrometer + Spring Boot Actuator's auto-instrumentation emits
`http_server_requests_seconds` (a Timer/histogram) with labels `uri`,
`method`, `status`, `outcome`. The recording rule `label_replace`s `uri`
→ `route` and `status` → `status_code` — like the modern .NET case, this
is auto-instrumented, you don't hand-roll counters.

### Setup

`pom.xml`:
```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-actuator</artifactId>
</dependency>
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-prometheus</artifactId>
</dependency>
```

`application.properties`:
```properties
management.endpoints.web.exposure.include=prometheus
management.endpoint.prometheus.enabled=true
management.metrics.distribution.percentiles-histogram.http.server.requests=true
```

That's it for inbound requests — Spring Boot Actuator auto-instruments
every controller endpoint. For outbound calls (populating the "External
Dependency Latency" panel), wrap your `RestTemplate`/`WebClient` with
Micrometer's HTTP client instrumentation so it emits
`http_client_requests_seconds` — check your Spring Boot version's docs,
this is usually auto-configured if you're using
`RestTemplateBuilder`/`WebClient.Builder` from the Spring context rather
than constructing the client directly.

### Verify before handoff

```bash
curl http://localhost:PORT/actuator/prometheus | grep -E '^http_server_requests_seconds'
```
Confirm `uri=`, `status=`, and `outcome=` labels appear, and that `uri`
values are route templates (Spring does this by default —
`/api/orders/{id}`, not `/api/orders/12345`).

---

## Authentication

Whatever stack you're on, decide how the platform team's Prometheus
should authenticate to your `/metrics` endpoint — this is a separate
concern from the metric shape above, and you'll need to tell the platform
team which one you're using (see `onboarding-consumer-app.md` step 4):

- **Bearer token** — simplest, most common on this platform today.
  Generate a token, put it behind your normal auth middleware on the
  `/metrics` route specifically, hand the token to the platform team via
  a secret (not chat/email) for them to store as a Prometheus
  `credentials_file`.
- **Basic auth** — also supported, same secret-handling rule applies.
- **None** — acceptable only if `/metrics` is unreachable from outside
  your private network already (e.g. internal-only VPC, no public
  ingress) — don't leave metrics endpoints open with no auth on anything
  internet-reachable.

## After you're done: verify against the recording rule yourself

Before asking the platform team to onboard your app, open the recording
rule file for your `app_type` and compare it line-by-line against your
own `curl`'d output — the tables above summarize the common case, but the
rule file is the authoritative source (and documents any additional
edge cases discovered since this doc was written). If your output doesn't
match and you can't easily change your instrumentation to fit, flag it to
the platform team — they can extend the recording rule to recognize a new
shape (as happened for the `dotnet-framework` case above), but that's far
faster to sort out *before* onboarding than after a dashboard silently
shows nothing.
