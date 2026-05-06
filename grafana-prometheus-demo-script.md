# Prometheus + Grafana — Live Demo Script
### *5–10 Minute Presentation Guide · First-Time Audience*

---

> Hi everyone, I’m Vik Singh. I supervise the HR and Finance team, and today I’m excited to show you how we are trying to achive observability using Grafana & Prometheus. Let’s dive in.

## The One-Line Hook *(say this first)*
> *Disclaimer - What I am going to show  you is a demo environment, all data is simulated.


> *"Every minute your team spends guessing why something is broken is a minute your users are experiencing it. What I'm about to show you is the attempt how we eliminate that guessing — across every application in our portfolio, from a single screen." 
*

---

## Act 1 — The Portfolio at a Glance *(2 min)*
**Dashboard: Application Portfolio Overview**

### What to show

**1. Point to the app cards (60 seconds)**

> *"This is an example of our team's application portfolio — 10 applications are being monitored, which is a fraction of our application portfolio. 6 web apps and 4 apis.  Every application card shows you two things instantly: the uptime percentage over selected period, and whether that application is UP or DOWN right now. "*

- **green card** → *"Green means healthy — uptime above 99%. "*
- **yellow or red** → *"This is exactly what we want to catch before users call the helpdesk."*
- Click the card's background → *"And if I want to investigate any application, one click takes me straight into the deep analytics. We'll do that in a moment."*

**2. Scroll to the Uptime Bargauge (45 seconds)**

> *"Down here is the portfolio health summary — every application ranked by uptime, worst performers at the top."*

- Point to the bar lengths and colours → *"The colour coding is automatic. Green is healthy, yellow is degraded, red is down."*
- Point to sorting → *"It's sorted ascending — the most problematic applications surface to the top automatically."*

---

## Act 2 — Drilling Into an Application *(2–3 min)*
**Dashboard: 4-Layer Observability → Layer 1 (Golden Signals)**

### Transition
> *"Let's click into one of these applications and see what's actually happening under the hood."*

Click any app card → child dashboard opens, **Layer 1 auto-expanded**.

---

### Layer 1 — The Four Golden Signals (90 seconds)

> I won't cover all panels and features, just the most important ones. 

> *"The first thing you see when you open any application is the Four Golden Signals — a framework from Google's Site Reliability Engineering team. These four metrics tell you everything you need to know about whether a system is healthy, regardless of what technology it's built on."*

**Walk each panel briefly:**

| Panel | What to say |
|---|---|
| **Latency p50/p95/p99** | *"How fast is it? Notice we track three percentiles — not just an average. The p99 line tells you the experience of your worst-affected 1% of users. Averages hide problems. Percentiles don't."* |
| **Traffic — RPS** | *"How much load is it handling right now? Watch this line. A sudden drop here is just as alarming as a spike."* |
| **Error Rate 4xx/5xx** | *"Is it failing? We separate client errors from server errors because they have completely different root causes and possibly different owners."* |
| **Saturation** | *"Is the application running out of capacity? This shows database connection pool pressure — memory and cpu usage  "* |


**Run the script to spike up CPU usage"** -> 
```
docker run -it --rm -v "${PWD}:/app" -w /app python:3.9 python stress_demo.py
```

**Key demo moment — hover over the latency chart:**
> *"Watch what happens when I hover — I get every percentile at that exact moment in time. And if I click a spike, it links me directly to the endpoint breakdown — showing me which specific API route caused the problem."*

---

### Layer 2 — Infrastructure (30 seconds)
> *"One level down is real host-level data — CPU, memory, disk, network — scraped directly from the operating system. "*

- Point to CPU graph → *"Real CPU utilisation, updated every 15 seconds."*
- Point to memory → *"Memory used vs available. The moment swap usage appears, we get an immediate alert — swap means the OS is treating disk as RAM, which degrades performance by 100 times."*

---

### Layer 3 — Application Layer (45 seconds)
> *"This is where it gets interesting — the application's own behaviour."*

**Point to Request Rate by Endpoint:**
> *"We can see exactly which API routes are being called and how many times per second. "*

**Point to Error Rate by Status Code:**
> *"And errors — broken down by HTTP status code. A spike in 500s means the server is crashing. A spike in 429s means we're hitting a rate limit on a downstream dependency. Completely different problems, visible at a glance."*

**Click a data point on the error chart:**
> *"And here's the drill-down — I can click any data point and get the endpoint breakdown: which operation, how many errors, how long it's taking. The slowest or most broken operations surface to the top."*

---

### Layer 5 — Database (45 seconds)
> *"Databases are the most common bottleneck and the hardest to diagnose."*

**Point to Query Latency:**
> *"Query latency at the 95th and 99th percentile — not just 'the database is slow' but specifically which queries are slow, how slow, and when it started."*

**Point to Active Connections:**
> *"And connection pool saturation — how full the database connection pool is. When this hits 90%, applications start timing out. We alert at 70% so we have time to react."*

**Point to Replication Lag:**
> *"Replication lag — the delay between the primary database and its replicas. If this climbs above 60 seconds and the primary fails, that's how much data we lose. Knowing about it in advance means we can act before that scenario happens."*


---

## Act 3 — The Information Layer *(30 seconds)*
> *"One more thing — every single chart has built-in documentation."*

**Click the ⓘ info icon on any panel:**
> *"Click the information icon on any panel and you get a plain-English explanation of what this metric means, why it matters, how it's collected, what the thresholds are, and what the common causes of problems are. The knowledge is embedded in the tool."*

---

## Closing Statement *(30 seconds)*

> *"What you've seen in the last few minutes is a single pane of glass across our entire application portfolio — from a high-level portfolio health view down to individual database queries and API endpoints, all connected, all real-time, all with built-in context."*

> *"The alternative is what most teams do today: waiting for users to report problems, then spending hours SSHing into servers, reading log files, and piecing together what happened. This platform changes that. We see problems forming before users feel them — and when something does go wrong, we know exactly where to look within seconds."*

> *"This is the foundation of everything we want to build in centralized monitoring."*

> Finally, I want to give as huge shoutout to Ryan Large in our team for all the help in exploring, learning, developing and setting up this new monitoring tools. 

> Thank you Ryan and thank you all for listening.

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
