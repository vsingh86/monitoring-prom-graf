# Centralized Monitoring Demo Stack

A fully self-contained Prometheus + Grafana demo with realistic simulated
metrics across all 6 observability layers — plus real host metrics from your
own machine via node_exporter.

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- Ports 3000, 9090, 9100, 9999 free on localhost

---

## Quick Start

```bash
# 1. Start the stack
docker compose up -d --build

# 2. Wait ~15 seconds for Prometheus to scrape the first samples

# 3. Open Grafana
open http://localhost:3000
# Login: admin / demo1234
# The dashboard loads automatically as the home screen
```

---

## What's Running

| Container      | URL                          | Purpose                                |
|----------------|------------------------------|----------------------------------------|
| grafana        | http://localhost:3000        | Dashboard UI (auto-provisioned)        |
| prometheus     | http://localhost:9090        | Metrics storage & query engine         |
| node-exporter  | http://localhost:9100/metrics| Real CPU / memory / disk / network     |
| fake-exporter  | http://localhost:9999/metrics| Simulated app metrics (all 6 layers)   |

---

## Simulated Incident Patterns

The fake exporter automatically injects realistic incidents every 1.5–3 minutes.
Each lasts 2–5 minutes then recovers. Watch the dashboard for:

| Incident           | What you'll see                                                   |
|--------------------|-------------------------------------------------------------------|
| `traffic_spike`    | RPS doubles, latency climbs, queue depth grows, connection pools fill |
| `error_surge`      | 5xx rate jumps to 15%+, Stripe probe goes DOWN, webhook failures  |
| `memory_pressure`  | JVM heap climbs toward max, Redis hit ratio drops to ~55%         |
| `slow_query`       | DB query p99 spikes 10–40×, replication lag grows, exclusive locks increase |
| `gc_storm`         | JVM GC pause p99 spikes above 1s, heap fluctuates wildly          |

Set the dashboard time range to **Last 30 minutes** and refresh to **10s**
for the best demo effect.

---

## Layer-by-Layer Guide for Your Demo

### 🟣 Layer 1 — Golden Signals (top of dashboard)
- Point to the **latency p99** panel — show how the 99th percentile tells a
  different story than the median during incidents
- The **error rate** panel shows 4xx vs 5xx separately — different root causes
- **Saturation** shows connection pool pressure, not just CPU

### 🟢 Layer 2 — Infrastructure (real data from your machine)
- These panels show **actual** CPU, memory, disk, and network from the host
  running Docker — genuinely real data, not simulated
- Great for showing that infrastructure monitoring is a baseline, not the full picture

### 🟡 Layer 3 — Application
- **Business transactions** panel shows orders/payments/logins — this is what
  the business actually cares about
- **Queue depth** climbs visibly during traffic_spike incidents
- **Endpoint breakdown** shows which routes are under load

### 🔴 Layer 4 — Runtime (JVM + Node.js)
- **GC pause time** is invisible at the OS level — only visible here
- **Heap %** shows memory_pressure incidents before they cause OOM
- **Event loop lag** simulates a Node.js service running alongside the JVM app

### 🔵 Layer 5 — Database
- **Query latency** spikes dramatically during slow_query incidents
- **Replication lag** is a leading indicator — watch it climb before the
  application starts returning stale data
- **Redis cache hit ratio** drops during memory_pressure (evictions increase)

### ⚫ Layer 6 — SaaS / External
- **Availability stat panel** turns RED when an error_surge hits Stripe
- **Rate limit consumption** shows the quota draining and refilling — great
  for showing the value of monitoring third-party dependencies

---

## Customising the Simulated Metrics

Edit `fake-exporter/main.py`:

- **Change incident frequency**: adjust `time.sleep(random.uniform(90, 180))`
- **Change baseline RPS**: adjust `sine_wave(3600, 60, 120)` (period, amplitude, offset)
- **Add a new endpoint**: add it to the `ENDPOINTS` list with a weight
- **Change metric names**: update both `main.py` and the Grafana dashboard JSON

After editing, rebuild with:
```bash
docker compose up -d --build fake-exporter
```

---

## Stopping the Stack

```bash
docker compose down          # stop containers, keep data volumes
docker compose down -v       # stop containers AND delete data
```

---

## Connecting Real Applications Later

To add your real apps alongside the demo:

1. Add a new scrape job to `prometheus/prometheus.yml`
2. Run `curl -X POST http://localhost:9090/-/reload` to hot-reload Prometheus
3. Build new panels in Grafana pointing at your real metric names

No restart required.
