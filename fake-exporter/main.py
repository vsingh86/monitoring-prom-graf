#!/usr/bin/env python3
"""
Fake Metrics Exporter — Multi-App Demo
Simulates realistic per-app metrics so the parent dashboard shows
varied health states across the application portfolio.
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
APPS = {
    "orders-api":         { "base_rps": 140, "base_lat": 0.09, "err": 0.004, "incident_risk": 0.30, "phase": 0.0 },
    "payments-service":   { "base_rps": 60,  "base_lat": 0.18, "err": 0.002, "incident_risk": 0.15, "phase": 1.1 },
    "user-portal":        { "base_rps": 200, "base_lat": 0.06, "err": 0.008, "incident_risk": 0.40, "phase": 2.2 },
    "inventory-service":  { "base_rps": 80,  "base_lat": 0.12, "err": 0.003, "incident_risk": 0.25, "phase": 3.3 },
    "notification-worker":{ "base_rps": 30,  "base_lat": 0.25, "err": 0.015, "incident_risk": 0.50, "phase": 4.4 },
    "auth-gateway":       { "base_rps": 300, "base_lat": 0.03, "err": 0.001, "incident_risk": 0.10, "phase": 5.5 },
}

ENDPOINTS = ["/api/v1/list", "/api/v1/get", "/api/v1/create", "/api/v1/update", "/health"]
UPSTREAMS = ["database", "cache", "external-api", "message-queue"]
SAAS_TARGETS = ["https://api.stripe.com", "https://api.salesforce.com"]

# ── Per-app incident simulator ─────────────────────────────────────────────────
class AppIncident:
    TYPES = ["error_surge", "latency_spike", "memory_pressure", "traffic_spike"]

    def __init__(self, app_name, risk):
        self.risk = risk
        self.active = {}
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        time.sleep(random.uniform(15, 90))
        while True:
            gap = random.uniform(60, 300) / (self.risk + 0.1)
            time.sleep(gap)
            itype = random.choice(self.TYPES)
            self.active[itype] = now() + random.uniform(90, 240)

    def active_types(self):
        expired = [k for k, v in self.active.items() if now() > v]
        for k in expired: del self.active[k]
        return list(self.active.keys())

    def severity(self, itype):
        rem = self.active.get(itype, 0) - now()
        return max(0.0, min(1.0, rem / 90))

incidents = { app: AppIncident(app, cfg["incident_risk"]) for app, cfg in APPS.items() }

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
    "http_client_request_duration_seconds", "Outbound latency",
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
jvm_mem_used = Gauge("jvm_memory_used_bytes",  "JVM heap used",  ["job","app","area","id"])
jvm_mem_max  = Gauge("jvm_memory_max_bytes",   "JVM heap max",   ["job","app","area","id"])
jvm_gc_pause = Histogram(
    "jvm_gc_pause_seconds", "GC pause",
    ["job","app","action"],
    buckets=[.001,.005,.01,.05,.1,.25,.5,1,2]
)
jvm_threads  = Gauge("jvm_threads_live_threads", "JVM threads",    ["job","app"])
hikar_active = Gauge("hikaricp_connections_active", "Pool active", ["job","app","pool"])
hikar_max    = Gauge("hikaricp_connections_max",    "Pool max",    ["job","app","pool"])
node_el_lag  = Gauge("nodejs_eventloop_lag_seconds","Event loop lag",["job","app"])
app_open_fds = Gauge("app_open_fds", "Open FDs (simulated)", ["job","app"])
app_max_fds  = Gauge("app_max_fds",  "Max FDs (simulated)",  ["job","app"])
pg_conns     = Gauge("pg_stat_activity_count",      "PG connections", ["job","app","datname"])
pg_max_conns = Gauge("pg_settings_max_connections", "PG max conns",   ["job","app","datname"])
pg_repl_lag  = Gauge("pg_replication_lag",          "PG repl lag",    ["job","app","instance"])
pg_db_size   = Gauge("pg_database_size_bytes",      "PG db size",     ["job","app","datname"])
pg_locks     = Gauge("pg_locks_count",              "PG locks",       ["job","app","datname","mode"])
redis_hits   = Counter("redis_keyspace_hits_total",   "Redis hits",   ["job","app"])
redis_misses = Counter("redis_keyspace_misses_total", "Redis misses", ["job","app"])
pg_query_lat = Histogram(
    "pg_stat_statements_total_exec_time", "PG query time ms",
    ["job","app"],
    buckets=[1,5,10,25,50,100,250,500,1000,2500]
)
probe_ok  = Gauge("probe_success",               "Probe up/down", ["job","app","target"])
probe_lat = Gauge("probe_http_duration_seconds", "Probe latency", ["job","app","target"])
rl_remain = Gauge("external_api_rate_limit_remaining", "RL remaining", ["job","app","service"])
rl_total  = Gauge("external_api_rate_limit_total",     "RL total",     ["job","app","service"])
wh_ok     = Counter("webhook_delivery_success_total", "Webhook ok",      ["job","app","service"])
wh_total  = Counter("webhook_delivery_total",         "Webhook attempts", ["job","app","service"])
app_uptime_ratio = Gauge(
    "app_uptime_ratio",
    "Rolling availability ratio (0-1). Used by overview dashboard.",
    ["job", "app"]
)

# ── Per-app mutable state ──────────────────────────────────────────────────────
app_state = {
    app: {
        "heap_mb": random.uniform(400, 800),
        "db_size_gb": random.uniform(2, 10),
        "queue_depths": {"default": random.uniform(20, 150), "priority": random.uniform(5, 50)},
        "rate_limits": {"stripe": random.randint(700,1000), "salesforce": random.randint(600,1000)},
        "uptime_score": random.uniform(0.97, 1.0),
    }
    for app in APPS
}

def update_app(app, cfg):
    inc   = incidents[app]
    state = app_state[app]
    active = inc.active_types()

    base_rps = noisy(sine(3600, cfg["base_rps"]*0.4, cfg["base_rps"], cfg["phase"]))
    if "traffic_spike" in active:
        base_rps *= (2 + inc.severity("traffic_spike") * 1.5)

    for _ in range(max(1, int(base_rps / 5))):
        ep     = random.choices(ENDPOINTS, weights=[30,25,20,15,5])[0]
        method = random.choices(["GET","POST","PUT"], weights=[60,25,15])[0]
        lat    = noisy(cfg["base_lat"] * {"GET":1,"POST":1.6,"PUT":1.3}.get(method,1), 0.35)
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
        if "latency_spike" in active and up == "database": dep_lat *= 4
        http_client_duration.labels(job=app, app=app, upstream=up).observe(dep_lat)

    for q, depth in state["queue_depths"].items():
        if "traffic_spike" in active:
            state["queue_depths"][q] = min(8000, depth + random.uniform(3, 30))
        else:
            state["queue_depths"][q] = max(5, depth * 0.97 + random.uniform(-3, 5))
        queue_depth_g.labels(job=app, app=app, queue=q).set(state["queue_depths"][q])
        job_proc_secs.labels(job=app, app=app, queue=q).observe(noisy(1.5, 0.4))

    ht = 512 + sine(600, 180, 0, cfg["phase"])
    if "memory_pressure" in active: ht += 350 + inc.severity("memory_pressure") * 500
    state["heap_mb"] = state["heap_mb"] * 0.85 + ht * 0.15
    if state["heap_mb"] > 1350: state["heap_mb"] *= 0.62

    jvm_mem_used.labels(job=app, app=app, area="heap", id="Eden").set(state["heap_mb"]*0.6*1024**2)
    jvm_mem_used.labels(job=app, app=app, area="heap", id="OldGen").set(state["heap_mb"]*0.4*1024**2)
    jvm_mem_max.labels(job=app, app=app, area="heap", id="Eden").set(2048*1024**2)
    jvm_mem_max.labels(job=app, app=app, area="heap", id="OldGen").set(2048*1024**2)

    gc_p = noisy(0.018, 0.5)
    if "memory_pressure" in active: gc_p = noisy(0.7 + inc.severity("memory_pressure")*1.2, 0.3)
    jvm_gc_pause.labels(job=app, app=app, action="minor GC").observe(gc_p)
    if random.random() < 0.04:
        jvm_gc_pause.labels(job=app, app=app, action="major GC").observe(gc_p * 5)

    lt = noisy(60 + base_rps * 0.25)
    if "traffic_spike" in active: lt *= 1.4
    jvm_threads.labels(job=app, app=app).set(lt)

    pa = noisy(min(44, 4 + base_rps * 0.18))
    if "traffic_spike" in active: pa = min(49, pa * 2)
    hikar_active.labels(job=app, app=app, pool=f"{app}-pool").set(pa)
    hikar_max.labels(job=app, app=app, pool=f"{app}-pool").set(50)

    el = noisy(0.004, 0.5)
    if "latency_spike" in active: el = noisy(0.25 + inc.severity("latency_spike")*0.35, 0.3)
    node_el_lag.labels(job=app, app=app).set(el)
    app_open_fds.labels(job=app, app=app).set(noisy(280 + base_rps * 0.4))
    app_max_fds.labels(job=app, app=app).set(65536)

    dbc = noisy(12 + base_rps * 0.12)
    if "traffic_spike" in active: dbc = min(92, dbc * 2)
    pg_conns.labels(job=app, app=app, datname=f"{app}-db").set(dbc)
    pg_max_conns.labels(job=app, app=app, datname=f"{app}-db").set(100)

    repl = noisy(0.6, 0.5)
    if "latency_spike" in active or "traffic_spike" in active:
        repl = noisy(12 + inc.severity("latency_spike")*40, 0.3)
    pg_repl_lag.labels(job=app, app=app, instance=f"{app}-replica").set(repl)

    state["db_size_gb"] += 0.000008
    pg_db_size.labels(job=app, app=app, datname=f"{app}-db").set(state["db_size_gb"]*1024**3)

    ql = noisy(20 if "latency_spike" not in active else 300 + inc.severity("latency_spike")*700, 0.4)
    pg_query_lat.labels(job=app, app=app).observe(ql)
    pg_locks.labels(job=app, app=app, datname=f"{app}-db", mode="ExclusiveLock").set(
        noisy(2 + (15 if "latency_spike" in active else 0)))

    hr = 0.91
    if "memory_pressure" in active: hr = 0.52 + inc.severity("memory_pressure")*0.25
    calls = max(1, int(noisy(base_rps * 1.4)))
    redis_hits.labels(job=app, app=app).inc(int(calls * hr))
    redis_misses.labels(job=app, app=app).inc(int(calls * (1 - hr)))

    for tgt in SAAS_TARGETS:
        fp = 0.01
        if "error_surge" in active and "stripe" in tgt: fp = 0.35
        up = 0 if random.random() < fp else 1
        probe_ok.labels(job=app, app=app, target=tgt).set(up)
        probe_lat.labels(job=app, app=app, target=tgt).set(noisy(0.11,0.4) if up else noisy(5,0.2))

    for svc, quota in [("stripe",1000),("salesforce",1000)]:
        state["rate_limits"][svc] = max(0, state["rate_limits"][svc] - random.uniform(0.5, 5))
        if random.random() < 0.04: state["rate_limits"][svc] = quota
        rl_remain.labels(job=app, app=app, service=svc).set(state["rate_limits"][svc])
        rl_total.labels(job=app, app=app, service=svc).set(quota)

    wa = max(1, int(noisy(4)))
    ws = max(0, wa - (1 if "error_surge" in active and random.random() < 0.4 else 0))
    wh_total.labels(job=app, app=app, service="stripe").inc(wa)
    wh_ok.labels(job=app, app=app, service="stripe").inc(ws)

    # Uptime score: degrade during incidents, slowly recover otherwise
    penalty = 0.0
    if "error_surge"   in active: penalty += inc.severity("error_surge") * 0.04
    if "latency_spike" in active: penalty += inc.severity("latency_spike") * 0.015
    state["uptime_score"] = max(0.80, min(1.0, state["uptime_score"] - penalty + 0.0002))
    app_uptime_ratio.labels(job=app, app=app).set(state["uptime_score"])


def update_loop():
    while True:
        for app, cfg in APPS.items():
            try: update_app(app, cfg)
            except Exception as e: print(f"[error] {app}: {e}")
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
    print(f"Multi-app fake exporter — {len(APPS)} apps")
    for a in APPS: print(f"  • {a}")
    threading.Thread(target=update_loop, daemon=True).start()
    HTTPServer(("0.0.0.0", 9999), Handler).serve_forever()
