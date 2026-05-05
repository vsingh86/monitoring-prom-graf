# Prometheus + Grafana — Live Demo Script
### *5–10 Minute Presentation Guide · First-Time Audience*

---

> **Before you start:** Stack running? Open two browser tabs — **Overview dashboard** and **6-Layer Observability dashboard**. Set time range to **Last 30 minutes**, auto-refresh **15s**. Incidents fire every 90–180 seconds — let it run 5 minutes before the demo so there is already history in the graphs.

---

## The One-Line Hook *(say this first)*

> *"Every minute your team spends guessing why something is broken is a minute your users are experiencing it. What I'm about to show you is how we eliminate that guessing — across every application in our portfolio, from a single screen."*

---

## Act 1 — The Portfolio at a Glance *(2 min)*
**Dashboard: Application Portfolio Overview**

### What to show

**1. Point to the app cards (60 seconds)**

> *"This is our entire application portfolio — 10 systems, two tiers: web applications and APIs. Every card shows you two things instantly: the uptime percentage over the last hour, and whether that application is UP or DOWN right now. No need to log into 10 different systems, check 10 different dashboards, or wait for a user to report a problem."*

- Point to a **green card** → *"Green means healthy — uptime above 99%."*
- If any card is **yellow or red** → *"This is exactly what we want to catch before users call the helpdesk."*
- Click the card's background → *"And if I want to investigate any application, one click takes me straight into the deep analytics. We'll do that in a moment."*

**2. Scroll to the Uptime Bargauge (45 seconds)**

> *"Down here is the portfolio health summary — every application ranked by uptime, worst performers at the top. In a real incident, this tells the on-call engineer in under three seconds which system needs attention. No spreadsheet, no status meeting, no email chain."*

- Point to the bar lengths and colours → *"The colour coding is automatic. Green is healthy, yellow is degraded, red is down."*
- Point to sorting → *"It's sorted ascending — the most problematic applications surface to the top automatically."*

**3. The 'wow' moment — wait for an incident (30 seconds)**

> *"Watch what happens when an application degrades..."*

- If a card flips yellow/red during the demo → *"There it is. The card just changed. The uptime percentage dropped and the status flipped. That happened in real time — no manual check, no polling, no alert email that arrives five minutes late."*

---

## Act 2 — Drilling Into an Application *(2–3 min)*
**Dashboard: 5-Layer Observability → Layer 1 (Golden Signals)**

### Transition
> *"Let's click into one of these applications and see what's actually happening under the hood."*

Click any app card → child dashboard opens, **Layer 1 auto-expanded**.

---

### Layer 1 — The Four Golden Signals (90 seconds)

> *"The first thing you see when you open any application is the Four Golden Signals — a framework from Google's Site Reliability Engineering team. These four metrics tell you everything you need to know about whether a system is healthy, regardless of what technology it's built on."*

**Walk each panel briefly:**

| Panel | What to say |
|---|---|
| **Latency p50/p95/p99** | *"How fast is it? Notice we track three percentiles — not just an average. The p99 line tells you the experience of your worst-affected 1% of users. Averages hide problems. Percentiles don't."* |
| **Traffic — RPS** | *"How much load is it handling right now? Watch this line — it follows a realistic business-hours pattern. A sudden drop here is just as alarming as a spike."* |
| **Error Rate 4xx/5xx** | *"Is it failing? We separate client errors from server errors because they have completely different root causes and different owners."* |
| **Saturation** | *"Is it running out of capacity? This shows database connection pool pressure — when this approaches 100%, requests start queuing and latency explodes."* |


**Run the script to spike up CPU usage"** -> 
**Show the information button while CPU is spiking  
```
docker run -it --rm -v "${PWD}:/app" -w /app python:3.9 python stress_demo.py
```

**Key demo moment — hover over the latency chart:**
> *"Watch what happens when I hover — I get every percentile at that exact moment in time. And if I click a spike, it links me directly to the endpoint breakdown — showing me which specific API route caused the problem."*

---

### Layer 2 — Infrastructure (30 seconds)
> *"One level down is real host-level data — CPU, memory, disk, network — scraped directly from the operating system. This is your hardware heartbeat. Notice this is real data from the machine running this demo right now."*

- Point to CPU graph → *"Real CPU utilisation, updated every 15 seconds."*
- Point to memory → *"Memory used vs available. The moment swap usage appears, we get an immediate alert — swap means the OS is treating disk as RAM, which degrades performance by 100 times."*

---

### Layer 3 — Application Layer (45 seconds)
> *"This is where it gets interesting — the application's own behaviour."*

**Point to Request Rate by Endpoint:**
> *"We can see exactly which API routes are being called and how many times per second. In an incident, this tells us immediately whether it's one endpoint causing problems or the whole application."*

**Point to Error Rate by Status Code:**
> *"And errors — broken down by HTTP status code. A spike in 500s means the server is crashing. A spike in 429s means we're hitting a rate limit on a downstream dependency. Completely different problems, visible at a glance."*

**Click a data point on the error chart:**
> *"And here's the drill-down — I can click any data point and get the endpoint breakdown: which operation, how many errors, how long it's taking. The slowest or most broken operations surface to the top."*

---

### Layer 5 — Database (45 seconds)
> *"Databases are the most common bottleneck and the hardest to diagnose. Prometheus reaches into the database and surfaces what matters."*

**Point to Query Latency:**
> *"Query latency at the 95th and 99th percentile — not just 'the database is slow' but specifically which queries are slow, how slow, and when it started."*

**Point to Replication Lag:**
> *"Replication lag — the delay between the primary database and its replicas. If this climbs above 60 seconds and the primary fails, that's how much data we lose. Knowing about it in advance means we can act before that scenario happens."*

**Point to Active Connections:**
> *"And connection pool saturation — how full the database connection pool is. When this hits 90%, applications start timing out. We alert at 70% so we have time to react."*

---

## Act 3 — The Information Layer *(30 seconds)*
> *"One more thing — every single chart has built-in documentation."*

**Click the ⓘ info icon on any panel:**
> *"Click the information icon on any panel and you get a plain-English explanation of what this metric means, why it matters, how it's collected, what the thresholds are, and what the common causes of problems are. This is built into the dashboard — your team doesn't need to be a Prometheus expert to use it. The knowledge is embedded in the tool."*

---

## Act 4 — The 'Under the Hood' moment *(30 seconds — optional if time allows)*
> *"Everything you've seen is powered by two open-source tools that cost nothing to run."*

Open a new tab to `http://localhost:9090` (Prometheus UI):

> *"Prometheus is the engine. It scrapes metrics from every application and host every 15 seconds and stores them as time series. This is what feeds every panel in Grafana."*

Type in the expression bar:
```
app_uptime_ratio
```
> *"Every metric is queryable in real time. This is the same data powering the overview cards."*

Switch back to Grafana:
> *"Grafana is the intelligence layer on top — turning raw numbers into the dashboards, thresholds, colour coding, drill-downs, and documentation you just saw."*

---

## Closing Statement *(30 seconds)*

> *"What you've seen in the last few minutes is a single pane of glass across our entire application portfolio — from a high-level portfolio health view down to individual database queries and API endpoints, all connected, all real-time, all with built-in context."*

> *"The alternative is what most teams do today: waiting for users to report problems, then spending hours SSHing into servers, reading log files, and piecing together what happened. This platform changes that. We see problems forming before users feel them — and when something does go wrong, we know exactly where to look within seconds."*

> *"This is the foundation of everything we want to build in centralized monitoring."*

---

## Timing Guide

| Section | Time | Dashboard |
|---|---|---|
| Hook + Portfolio overview | 1:30 | Overview |
| App cards + incident demo | 1:30 | Overview |
| Drill-down intro | 0:30 | Child — Layer 1 |
| Golden Signals walkthrough | 1:30 | Child — Layer 1 |
| Infrastructure | 0:30 | Child — Layer 2 |
| Application layer + drill-down | 1:00 | Child — Layer 3 |
| Database | 0:45 | Child — Layer 5 |
| Info button | 0:30 | Any panel |
| Prometheus engine (optional) | 0:30 | Prometheus UI |
| Closing | 0:30 | — |
| **Total** | **~9 min** | |

---

## Anticipated Questions & Answers

**"How does it know when something is wrong?"**
> Prometheus evaluates alerting rules every 15 seconds. When a metric crosses a threshold — say error rate above 1% for 2 minutes — it fires an alert to Alertmanager, which routes it to Slack, PagerDuty, or email. The dashboards show you the state; the alerting notifies you proactively.

**"Can it monitor our legacy applications?"**
> Yes — that was a core design requirement. Legacy Java apps use JMX Exporter (zero code change). .NET apps use prometheus-net. Any app that writes logs can be monitored via log parsing. Windows servers use windows_exporter. If it produces any signal — HTTP traffic, logs, JMX, SNMP — Prometheus can collect it.

**"What happens when Prometheus or Grafana goes down?"**
> You monitor the monitors. Prometheus has its own health endpoint. For production, you run two Prometheus instances in parallel (federation) and use Grafana's alerting to page if Prometheus itself stops scraping. The demo stack is single-node; the production architecture would be highly available.

**"How do we add a new application?"**
> Add a scrape job to `prometheus.yml` (three lines of YAML), restart Prometheus to hot-reload the config. The application appears in the portfolio overview within 30 seconds. No dashboard changes required — the `app` label propagates automatically.

**"How is this different from what we have in SolarWinds?"**
> SolarWinds is excellent for network and infrastructure monitoring. Prometheus + Grafana goes deeper into the application layer — inside the JVM, into database query patterns, into individual API endpoints — and is far more flexible for custom metrics. The two can coexist; Prometheus can even scrape SNMP data from the same network devices SolarWinds monitors.

**"What's the cost?"**
> Prometheus and Grafana core are open source — the software is free. Costs are infrastructure (the servers running them) and engineering time to instrument applications. Grafana Cloud offers a managed option with a generous free tier if you don't want to operate the stack yourself.

---

## Pre-Demo Checklist

- [ ] Docker stack running (`docker compose up -d`)
- [ ] Waited at least 5 minutes for metric history to accumulate
- [ ] Browser tab 1: `http://localhost:3000` → Overview dashboard
- [ ] Browser tab 2: `http://localhost:3000/d/demo-monitoring-v1` → Child dashboard, pre-set to any app
- [ ] Time range: Last 30 minutes
- [ ] Auto-refresh: 15 seconds
- [ ] Screen resolution comfortable for audience (zoom browser to 80% if projecting)
- [ ] Prometheus UI open in tab 3: `http://localhost:9090` (for optional Act 4)
- [ ] Close all other browser tabs — clean, distraction-free presentation

---

*Demo stack: Prometheus v2.51 · Grafana v10.4 · Simulated metrics across 10 apps with automatic incident injection*
