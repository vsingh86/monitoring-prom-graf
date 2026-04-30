#!/usr/bin/env python3
"""
Fake Metrics Exporter — Organisation App Portfolio Demo
Simulates realistic per-app metrics for 10 applications across two tiers.
"""

import time, math, random, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from prometheus_client import (
    generate_latest, CONTENT_TYPE_LATEST, REGISTRY,
    Counter, Histogram, Gauge
)

def now(): return time.time()
def noisy(v, n=0.06): return max(0, v * (1 + random.gauss(0, n)))
def sine(period, amp, offset, phase=0):
    return offset + amp * math.sin(2 * math.pi * (now() / period) + phase)

# ── App definitions ────────────────────────────────────────────────────────────
# Web Apps: higher RPS, moderate latency
# APIs:     lower RPS, lower latency, tighter error budgets
APPS = {
    # Web Apps
    "CCMS":     { "base_rps": 120, "base_lat": 0.11, "err": 0.006, "risk": 0.30, "phase": 0.0  },
    "ECRS":     { "base_rps": 90,  "base_lat": 0.09, "err": 0.005, "risk": 0.25, "phase": 0.65 },
    "HIMS":     { "base_rps": 160, "base_lat": 0.13, "err": 0.007, "risk": 0.35, "phase": 1.30 },
    "ESS":      { "base_rps": 80,  "base_lat": 0.08, "err": 0.004, "risk": 0.20, "phase": 1.95 },
    "MARS":     { "base_rps": 55,  "base_lat": 0.15, "err": 0.009, "risk": 0.40, "phase": 2.60 },
    "SELF":     { "base_rps": 70,  "base_lat": 0.10, "err": 0.005, "risk": 0.22, "phase": 3.25 },
    # APIs
    "auth-api": { "base_rps": 310, "base_lat": 0.03, "err": 0.001, "risk": 0.10, "phase": 3.90 },
    "card-api": { "base_rps": 75,  "base_lat": 0.19, "err": 0.002, "risk": 0.18, "phase": 4.55 },
    "hims-api": { "base_rps": 95,  "base_lat": 0.12, "err": 0.003, "risk": 0.28, "phase": 5.20 },
    "ecrs-api": { "base_rps": 85,  "base_lat": 0.10, "err": 0.003, "risk": 0.23, "phase": 5.85 },
}

ENDPOINTS = ["/api/v1/list", "/api/v1/get", "/api/v1/create", "/api/v1/update", "/health"]
UPSTREAMS = ["database", "cache", "external-api", "message-queue"]

# ── Per-app incident simulator ─────────────────────────────────────────────────
class AppIncident:
    TYPES = ["error_surge", "latency_spike", "memory_pressure", "traffic_spike"]

    def __init__(self, risk):
        self.active = {}
        self.risk = risk
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        time.sleep(random.uniform(20, 120))
        while True:
            time.sleep(random.uniform(60, 300) / (self.risk + 0.1))
            itype = random.choice(self.TYPES)
            self.active[itype] = now() + random.uniform(90, 240)

    def active_types(self):
        for k in [k for k, v in self.active.items() if now() > v]:
            del self.active[k]
        return list(self.active.keys())

    def severity(self, itype):
        return max(0.0, min(1.0, (self.active.get(itype, 0) - now()) / 90))

incidents = { app: AppIncident(cfg["risk"]) for app, cfg in APPS.items() }

# ── Metrics ────────────────────────────────────────────────────────────────────
http_requests = Counter(
    "http_requests_total", "HTTP requests",
    ["job", "app", "handler", "method", "status"]
)
http_duration = Histogram(
    "http_request_duration_seconds", "HTTP latency",
    ["job", "app", "handler"],
    buckets=[.005,.01,.025,.05,.1,.25,.5,1,2.5,5,10]
)
http_client_duration = Histogram(
    "http_client_request_duration_seconds", "Outbound call latency",
    ["job", "app", "upstream"],
    buckets=[.01,.05,.1,.25,.5,1,2,5]
)
business_txns = Counter(
    "business_transactions_total", "Business transactions",
    ["job", "app", "type"]
)
queue_depth_g = Gauge("queue_depth", "Queue depth", ["job", "app", "queue"])
job_proc_secs = Histogram(
    "job_processing_seconds", "Job processing time",
    ["job", "app", "queue"],
    buckets=[.1,.5,1,2,5,10,30,60]
)
pg_conns     = Gauge("pg_stat_activity_count",      "PG connections", ["job","app","datname"])
pg_max_conns = Gauge("pg_settings_max_connections", "PG max conns",   ["job","app","datname"])
pg_repl_lag  = Gauge("pg_replication_lag",          "PG repl lag",    ["job","app","instance"])
pg_db_size   = Gauge("pg_database_size_bytes",      "PG db size",     ["job","app","datname"])
pg_locks     = Gauge("pg_locks_count",              "PG locks",       ["job","app","datname","mode"])
pg_query_lat = Histogram(
    "pg_stat_statements_total_exec_time", "PG query time ms",
    ["job","app"],
    buckets=[1,5,10,25,50,100,250,500,1000,2500]
)
app_uptime_ratio = Gauge(
    "app_uptime_ratio",
    "Rolling availability ratio (0-1). Historical uptime based on incident penalties.",
    ["job", "app", "tier"]
)
app_up = Gauge(
    "app_up",
    "Current app health: 1=UP (healthy right now), 0=DOWN (active severe incident). "
    "Independent of the rolling uptime score — reflects point-in-time state.",
    ["job", "app", "tier"]
)

# ── Per-app mutable state ──────────────────────────────────────────────────────
app_state = {
    app: {
        "db_size_gb":   random.uniform(2, 15),
        "queue_depths": {"default": random.uniform(20, 150), "priority": random.uniform(5, 50)},
        "uptime_score": random.uniform(0.97, 1.0),
    }
    for app in APPS
}

def update_app(app, cfg):
    inc    = incidents[app]
    state  = app_state[app]
    active = inc.active_types()
    tier   = "web-app" if app in ("CCMS","ECRS","HIMS","ESS","MARS","SELF") else "api"

    base_rps = noisy(sine(3600, cfg["base_rps"]*0.4, cfg["base_rps"], cfg["phase"]))
    if "traffic_spike" in active:
        base_rps *= (2 + inc.severity("traffic_spike") * 1.5)

    for _ in range(max(1, int(base_rps / 5))):
        ep     = random.choices(ENDPOINTS, weights=[30,25,20,15,5])[0]
        method = random.choices(["GET","POST","PUT"], weights=[60,25,15])[0]
        lat    = noisy(cfg["base_lat"] * {"GET":1.0,"POST":1.6,"PUT":1.3}.get(method,1.0), 0.35)
        if "latency_spike" in active:
            lat *= (4 + inc.severity("latency_spike") * 8)
        err_p = cfg["err"]
        if "error_surge" in active:
            err_p = min(0.5, err_p + inc.severity("error_surge") * 0.25)
        if random.random() < err_p:
            status = random.choices(["500","502","503","429"], weights=[50,20,20,10])[0]
        elif random.random() < 0.015:
            status = random.choice(["400","404"])
        else:
            status = "200"
        http_duration.labels(job=app, app=app, handler=ep).observe(lat)
        http_requests.labels(job=app, app=app, handler=ep, method=method, status=status).inc()

    for _ in range(max(0, int(noisy(base_rps * 0.06)))):
        business_txns.labels(job=app, app=app, type="transaction_completed").inc()

    for up in UPSTREAMS:
        dep_lat = noisy({"database":0.15,"cache":0.003,"external-api":0.22,"message-queue":0.08}.get(up,0.1), 0.4)
        if "latency_spike" in active and up == "database":
            dep_lat *= 4
        http_client_duration.labels(job=app, app=app, upstream=up).observe(dep_lat)

    for q, depth in state["queue_depths"].items():
        state["queue_depths"][q] = (
            min(8000, depth + random.uniform(3, 30)) if "traffic_spike" in active
            else max(5, depth * 0.97 + random.uniform(-3, 5))
        )
        queue_depth_g.labels(job=app, app=app, queue=q).set(state["queue_depths"][q])
        job_proc_secs.labels(job=app, app=app, queue=q).observe(noisy(1.5, 0.4))

    # DB
    dbc = noisy(12 + base_rps * 0.12)
    if "traffic_spike" in active: dbc = min(92, dbc * 2)
    pg_conns.labels(job=app, app=app, datname=f"{app}-db").set(dbc)
    pg_max_conns.labels(job=app, app=app, datname=f"{app}-db").set(100)

    repl = noisy(0.6, 0.5)
    if "latency_spike" in active or "traffic_spike" in active:
        repl = noisy(12 + inc.severity("latency_spike") * 40, 0.3)
    pg_repl_lag.labels(job=app, app=app, instance=f"{app}-replica").set(repl)

    state["db_size_gb"] += 0.000008
    pg_db_size.labels(job=app, app=app, datname=f"{app}-db").set(state["db_size_gb"] * 1024**3)

    ql = noisy(20 if "latency_spike" not in active else 300 + inc.severity("latency_spike") * 700, 0.4)
    pg_query_lat.labels(job=app, app=app).observe(ql)
    pg_locks.labels(job=app, app=app, datname=f"{app}-db", mode="ExclusiveLock").set(
        noisy(2 + (15 if "latency_spike" in active else 0))
    )

    # Uptime % — rolling score, degrades during incidents, recovers slowly
    penalty = 0.0
    if "error_surge"   in active: penalty += inc.severity("error_surge")   * 0.04
    if "latency_spike" in active: penalty += inc.severity("latency_spike") * 0.015
    state["uptime_score"] = max(0.80, min(1.0, state["uptime_score"] - penalty + 0.0002))
    app_uptime_ratio.labels(job=app, app=app, tier=tier).set(state["uptime_score"])

    # Current Status — binary, independent of rolling uptime.
    # DOWN (0) when an error_surge incident is active with severity > 0.4.
    # Recovers to UP (1) the moment the incident clears.
    is_up = 0.0 if ("error_surge" in active and inc.severity("error_surge") > 0.4) else 1.0
    app_up.labels(job=app, app=app, tier=tier).set(is_up)


def update_loop():
    while True:
        for app, cfg in APPS.items():
            try:
                update_app(app, cfg)
            except Exception as e:
                print(f"[error] {app}: {e}")
        time.sleep(1)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/metrics"):
            out = generate_latest(REGISTRY)
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(out)
        elif self.path == "/health":
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
        else:
            self.send_response(404); self.end_headers()

    def log_message(self, *a): pass


if __name__ == "__main__":
    print(f"Fake exporter — {len(APPS)} apps")
    for a in APPS: print(f"  • {a}")
    threading.Thread(target=update_loop, daemon=True).start()
    HTTPServer(("0.0.0.0", 9999), Handler).serve_forever()
