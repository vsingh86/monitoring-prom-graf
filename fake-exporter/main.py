#!/usr/bin/env python3
"""
Fake Metrics Exporter — Centralized Monitoring Demo
Simulates realistic application metrics across all 6 observability layers.
Includes: traffic spikes, simulated incidents, GC pressure, slow queries, etc.
"""

import time
import math
import random
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from prometheus_client import (
    generate_latest, CONTENT_TYPE_LATEST, REGISTRY,
    Counter, Histogram, Gauge, Summary
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def now():
    return time.time()

def sine_wave(period_s, amplitude, offset, phase=0):
    """Smooth oscillating value — good for traffic patterns."""
    return offset + amplitude * math.sin(2 * math.pi * (now() / period_s) + phase)

def noisy(value, noise_pct=0.05):
    """Add realistic jitter to a value."""
    return max(0, value * (1 + random.gauss(0, noise_pct)))

# ── Incident Simulator ────────────────────────────────────────────────────────

class IncidentSimulator:
    """
    Randomly injects realistic incident patterns:
      - Traffic spike (sudden load increase)
      - Error surge (5xx rate spikes)
      - Memory pressure (heap climbs)
      - Slow queries (DB latency degrades)
      - GC storm (JVM GC pause spikes)
    Each incident lasts 2–5 minutes, then recovers.
    """
    def __init__(self):
        self.active = {}   # incident_type -> end_time
        self.types = ["traffic_spike", "error_surge", "memory_pressure", "slow_query", "gc_storm"]
        threading.Thread(target=self._scheduler, daemon=True).start()

    def _scheduler(self):
        while True:
            time.sleep(random.uniform(90, 180))   # incident every 1.5–3 min
            itype = random.choice(self.types)
            duration = random.uniform(120, 300)   # 2–5 minutes
            self.active[itype] = now() + duration
            print(f"[incident] {itype} started, duration={duration:.0f}s")

    def is_active(self, itype):
        end = self.active.get(itype, 0)
        active = now() < end
        if not active and itype in self.active:
            del self.active[itype]
        return active

    def severity(self, itype):
        """0.0–1.0 severity based on how far into the incident we are."""
        end = self.active.get(itype, 0)
        remaining = end - now()
        if remaining <= 0:
            return 0.0
        return min(1.0, remaining / 120)

incident = IncidentSimulator()

# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1 — Golden Signals
# ══════════════════════════════════════════════════════════════════════════════

# Latency histogram — used by dashboard for p50/p95/p99
http_request_duration = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["handler", "method", "status"],
    buckets=[.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10]
)

# Total requests counter — used for throughput and error rate
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["handler", "method", "status", "job"]
)

# External dependency (downstream calls)
http_client_request_duration = Histogram(
    "http_client_request_duration_seconds",
    "Outbound HTTP call latency",
    ["upstream"],
    buckets=[.01, .05, .1, .25, .5, 1, 2, 5]
)

# ══════════════════════════════════════════════════════════════════════════════
# LAYER 3 — Application
# ══════════════════════════════════════════════════════════════════════════════

business_transactions_total = Counter(
    "business_transactions_total",
    "Business domain transactions",
    ["type", "job"]
)

queue_depth = Gauge(
    "queue_depth",
    "Background job queue depth",
    ["queue", "job"]
)

job_processing_seconds = Histogram(
    "job_processing_seconds",
    "Background job processing time",
    ["queue"],
    buckets=[.1, .5, 1, 2, 5, 10, 30, 60]
)

# ══════════════════════════════════════════════════════════════════════════════
# LAYER 4 — JVM / Runtime
# ══════════════════════════════════════════════════════════════════════════════

jvm_memory_used_bytes = Gauge(
    "jvm_memory_used_bytes",
    "JVM memory used",
    ["area", "id", "job"]
)
jvm_memory_max_bytes = Gauge(
    "jvm_memory_max_bytes",
    "JVM memory max",
    ["area", "id", "job"]
)

jvm_gc_pause_seconds = Histogram(
    "jvm_gc_pause_seconds",
    "JVM GC pause duration",
    ["action", "cause", "job"],
    buckets=[.001, .005, .01, .05, .1, .25, .5, 1, 2]
)

jvm_threads_live_threads = Gauge(
    "jvm_threads_live_threads",
    "JVM live thread count",
    ["job"]
)
jvm_threads_daemon_threads = Gauge(
    "jvm_threads_daemon_threads",
    "JVM daemon thread count",
    ["job"]
)

hikaricp_connections_active = Gauge(
    "hikaricp_connections_active",
    "HikariCP active connections",
    ["pool", "job"]
)
hikaricp_connections_max = Gauge(
    "hikaricp_connections_max",
    "HikariCP max connections",
    ["pool", "job"]
)

nodejs_eventloop_lag_seconds = Gauge(
    "nodejs_eventloop_lag_seconds",
    "Node.js event loop lag",
    ["job"]
)

app_open_fds = Gauge("app_open_fds", "Open file descriptors (simulated)", ["job"])
app_max_fds  = Gauge("app_max_fds",  "Max file descriptors (simulated)",  ["job"])

# ══════════════════════════════════════════════════════════════════════════════
# LAYER 5 — Database
# ══════════════════════════════════════════════════════════════════════════════

pg_stat_activity_count   = Gauge("pg_stat_activity_count",   "PG active connections", ["datname"])
pg_settings_max_connections = Gauge("pg_settings_max_connections", "PG max connections", ["datname"])
pg_replication_lag        = Gauge("pg_replication_lag",        "PG replication lag seconds", ["job", "instance"])
pg_database_size_bytes    = Gauge("pg_database_size_bytes",    "PG database size bytes", ["datname"])
pg_locks_count            = Gauge("pg_locks_count",            "PG lock count", ["datname", "mode"])

mysql_global_status_innodb_deadlocks = Gauge(
    "mysql_global_status_innodb_deadlocks",
    "MySQL InnoDB deadlock count"
)

redis_keyspace_hits_total   = Counter("redis_keyspace_hits_total",   "Redis keyspace hits")
redis_keyspace_misses_total = Counter("redis_keyspace_misses_total", "Redis keyspace misses")

pg_stat_statements_total_exec_time = Histogram(
    "pg_stat_statements_total_exec_time",
    "PG query execution time (ms)",
    buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500]
)

# ══════════════════════════════════════════════════════════════════════════════
# LAYER 6 — SaaS / External
# ══════════════════════════════════════════════════════════════════════════════

probe_success = Gauge(
    "probe_success",
    "Blackbox probe result (1=up, 0=down)",
    ["target", "job"]
)
probe_http_duration_seconds = Gauge(
    "probe_http_duration_seconds",
    "Blackbox probe HTTP duration",
    ["target", "job"]
)

external_api_rate_limit_remaining = Gauge(
    "external_api_rate_limit_remaining",
    "API rate limit remaining calls",
    ["service", "job"]
)
external_api_rate_limit_total = Gauge(
    "external_api_rate_limit_total",
    "API rate limit total quota",
    ["service", "job"]
)

webhook_delivery_success_total = Counter(
    "webhook_delivery_success_total",
    "Webhook delivery successes",
    ["service", "job"]
)
webhook_delivery_total = Counter(
    "webhook_delivery_total",
    "Webhook delivery attempts",
    ["service", "job"]
)

# ══════════════════════════════════════════════════════════════════════════════
# Metric update thread
# ══════════════════════════════════════════════════════════════════════════════

ENDPOINTS = ["/api/orders", "/api/users", "/api/products", "/api/checkout", "/health"]
UPSTREAMS = ["payment-api", "auth-service", "inventory-api", "email-service"]
SAAS_TARGETS = ["https://api.stripe.com", "https://api.salesforce.com", "https://hooks.slack.com"]
QUEUES = ["email-send", "report-gen", "data-sync"]
JOB = "fake-app"
POOL = "orders-db-pool"

def update_metrics():
    # Persistent state
    heap_mb      = 512.0
    db_size_gb   = 4.2
    queue_depths = {q: random.uniform(50, 200) for q in QUEUES}
    rate_limits  = {"stripe": 900, "salesforce": 800, "slack": 950}

    while True:
        t = now()

        # ── Traffic shape: business hours sine + random spikes ──────────────
        base_rps = noisy(sine_wave(3600, 60, 120))   # 60–180 rps over 1-hr cycle
        if incident.is_active("traffic_spike"):
            base_rps *= (2.5 + incident.severity("traffic_spike"))

        # ── Layer 1: Golden Signals ──────────────────────────────────────────
        for _ in range(max(1, int(base_rps / 4))):
            endpoint = random.choices(ENDPOINTS, weights=[30,20,20,15,5])[0]
            method   = random.choices(["GET","POST","PUT"], weights=[60,25,15])[0]

            # Latency: baseline + incident degradation
            base_lat = {"GET": 0.08, "POST": 0.15, "PUT": 0.12}.get(method, 0.1)
            if incident.is_active("slow_query") and endpoint in ["/api/orders", "/api/checkout"]:
                base_lat *= (5 + incident.severity("slow_query") * 10)
            if incident.is_active("traffic_spike"):
                base_lat *= (1.5 + incident.severity("traffic_spike"))
            lat = noisy(base_lat, 0.3)

            # Error rate: normally ~0.5%, spikes to 15% during error_surge
            err_chance = 0.005
            if incident.is_active("error_surge"):
                err_chance = 0.05 + incident.severity("error_surge") * 0.15
            if random.random() < err_chance:
                status = random.choices(["500","502","503","429"], weights=[50,20,20,10])[0]
            elif random.random() < 0.02:
                status = random.choice(["400","404","422"])
            else:
                status = "200"

            http_request_duration.labels(handler=endpoint, method=method, status=status).observe(lat)
            http_requests_total.labels(handler=endpoint, method=method, status=status, job=JOB).inc()

        # Business transactions (subset of successful checkout requests)
        orders_rate = noisy(base_rps * 0.08)
        for _ in range(max(0, int(orders_rate))):
            business_transactions_total.labels(type="order_placed",   job=JOB).inc()
        for _ in range(max(0, int(orders_rate * 0.92))):
            business_transactions_total.labels(type="payment_success", job=JOB).inc()
        for _ in range(max(0, int(orders_rate * 0.3))):
            business_transactions_total.labels(type="user_login",      job=JOB).inc()

        # External dependency calls
        for upstream in UPSTREAMS:
            calls = max(1, int(noisy(base_rps * 0.25)))
            for _ in range(calls):
                dep_lat = noisy({"payment-api": 0.18, "auth-service": 0.04,
                                 "inventory-api": 0.12, "email-service": 0.22}.get(upstream, 0.1), 0.4)
                if upstream == "payment-api" and incident.is_active("error_surge"):
                    dep_lat *= 3
                http_client_request_duration.labels(upstream=upstream).observe(dep_lat)

        # ── Layer 3: Application / Queues ────────────────────────────────────
        for q in QUEUES:
            # Queues grow under traffic spike, drain normally
            if incident.is_active("traffic_spike"):
                queue_depths[q] = min(10000, queue_depths[q] + random.uniform(5, 50))
            else:
                queue_depths[q] = max(10, queue_depths[q] * 0.97 + random.uniform(-5, 8))
            queue_depth.labels(queue=q, job=JOB).set(queue_depths[q])

            proc_time = noisy({"email-send": 0.5, "report-gen": 8.0, "data-sync": 2.0}.get(q, 1.0), 0.3)
            job_processing_seconds.labels(queue=q).observe(proc_time)

        # ── Layer 4: JVM Runtime ─────────────────────────────────────────────
        # Heap: slowly climbs, GC resets it, memory_pressure incident causes climb
        heap_target = 512 + sine_wave(600, 200, 0)
        if incident.is_active("memory_pressure"):
            heap_target += 400 + incident.severity("memory_pressure") * 600
        heap_mb = heap_mb * 0.85 + heap_target * 0.15   # smooth

        # Simulate GC collection
        if heap_mb > 1400:
            heap_mb *= 0.6   # GC fires, heap drops

        jvm_memory_used_bytes.labels(area="heap", id="G1-Eden-Space", job=JOB).set(heap_mb * 0.6 * 1024 * 1024)
        jvm_memory_used_bytes.labels(area="heap", id="G1-Old-Gen",    job=JOB).set(heap_mb * 0.4 * 1024 * 1024)
        jvm_memory_max_bytes.labels(area="heap",  id="G1-Eden-Space", job=JOB).set(2048 * 1024 * 1024)
        jvm_memory_max_bytes.labels(area="heap",  id="G1-Old-Gen",    job=JOB).set(2048 * 1024 * 1024)

        # GC pauses — more frequent/longer during memory pressure or high heap
        gc_pause = noisy(0.02, 0.5)
        if incident.is_active("gc_storm"):
            gc_pause = noisy(0.8 + incident.severity("gc_storm") * 1.5, 0.3)
        if heap_mb > 1200:
            gc_pause = noisy(0.3, 0.4)
        jvm_gc_pause_seconds.labels(action="end of minor GC", cause="Allocation Failure", job=JOB).observe(gc_pause)
        if random.random() < 0.05 or incident.is_active("gc_storm"):
            jvm_gc_pause_seconds.labels(action="end of major GC", cause="G1 Humongous Allocation", job=JOB).observe(gc_pause * 4)

        # Threads
        live_threads = noisy(80 + base_rps * 0.3)
        if incident.is_active("traffic_spike"):
            live_threads *= 1.5
        jvm_threads_live_threads.labels(job=JOB).set(live_threads)
        jvm_threads_daemon_threads.labels(job=JOB).set(live_threads * 0.6)

        # HikariCP connection pool
        pool_active = noisy(min(45, 5 + base_rps * 0.2))
        if incident.is_active("traffic_spike"):
            pool_active = min(49, pool_active * 2)
        hikaricp_connections_active.labels(pool=POOL, job=JOB).set(pool_active)
        hikaricp_connections_max.labels(pool=POOL, job=JOB).set(50)

        # Node.js event loop (separate simulated service)
        el_lag = noisy(0.005, 0.5)
        if incident.is_active("traffic_spike"):
            el_lag = noisy(0.3 + incident.severity("traffic_spike") * 0.4, 0.3)
        nodejs_eventloop_lag_seconds.labels(job="node-api").set(el_lag)

        # File descriptors
        app_open_fds.labels(job=JOB).set(noisy(320 + base_rps * 0.5))
        app_max_fds.labels(job=JOB).set(65536)

        # ── Layer 5: Database ────────────────────────────────────────────────
        db_conns = noisy(15 + base_rps * 0.15)
        if incident.is_active("traffic_spike"):
            db_conns = min(95, db_conns * 2)
        pg_stat_activity_count.labels(datname="orders_db").set(db_conns)
        pg_stat_activity_count.labels(datname="users_db").set(noisy(8))
        pg_settings_max_connections.labels(datname="orders_db").set(100)
        pg_settings_max_connections.labels(datname="users_db").set(100)

        # Replication lag: normally <2s, spikes during incidents
        repl_lag = noisy(0.8, 0.5)
        if incident.is_active("traffic_spike") or incident.is_active("slow_query"):
            repl_lag = noisy(15 + incident.severity("traffic_spike") * 45, 0.2)
        pg_replication_lag.labels(job=JOB, instance="pg-replica-01").set(repl_lag)

        # DB size grows slowly
        db_size_gb += 0.00001
        pg_database_size_bytes.labels(datname="orders_db").set(db_size_gb * 1024**3)
        pg_database_size_bytes.labels(datname="users_db").set(1.1 * 1024**3)

        # Query latency
        q_lat = noisy(25 if not incident.is_active("slow_query") else
                      200 + incident.severity("slow_query") * 800, 0.4)
        pg_stat_statements_total_exec_time.observe(q_lat)

        # Locks & deadlocks
        pg_locks_count.labels(datname="orders_db", mode="ExclusiveLock").set(
            noisy(2 + (20 if incident.is_active("slow_query") else 0)))
        if incident.is_active("slow_query") and random.random() < 0.1:
            mysql_global_status_innodb_deadlocks.inc()

        # Redis cache hit ratio: normally ~92%, drops during memory_pressure
        hit_rate = 0.92
        if incident.is_active("memory_pressure"):
            hit_rate = 0.55 + incident.severity("memory_pressure") * 0.2
        redis_calls = max(1, int(noisy(base_rps * 1.5)))
        redis_keyspace_hits_total.inc(int(redis_calls * hit_rate))
        redis_keyspace_misses_total.inc(int(redis_calls * (1 - hit_rate)))

        # ── Layer 6: SaaS / External ─────────────────────────────────────────
        for target in SAAS_TARGETS:
            # Occasional probe failure (1% normally, higher during error_surge)
            fail_chance = 0.01
            if incident.is_active("error_surge") and "stripe" in target:
                fail_chance = 0.3
            up = 0 if random.random() < fail_chance else 1
            probe_success.labels(target=target, job="blackbox").set(up)
            probe_lat = noisy(0.12, 0.4) if up else noisy(5.0, 0.2)
            probe_http_duration_seconds.labels(target=target, job="blackbox").set(probe_lat)

        # Rate limits (drain and refill on a 60s window simulation)
        for svc, quota in [("stripe", 1000), ("salesforce", 1000), ("slack", 1000)]:
            rate_limits[svc] = max(0, rate_limits[svc] - random.uniform(1, 8))
            if random.random() < 0.05:   # periodic refill
                rate_limits[svc] = quota
            external_api_rate_limit_remaining.labels(service=svc, job=JOB).set(rate_limits[svc])
            external_api_rate_limit_total.labels(service=svc, job=JOB).set(quota)

        # Webhook delivery
        wh_attempts = max(1, int(noisy(5)))
        wh_success  = max(0, wh_attempts - (1 if incident.is_active("error_surge") and random.random() < 0.4 else 0))
        for svc in ["stripe", "github"]:
            webhook_delivery_total.labels(service=svc, job=JOB).inc(wh_attempts)
            webhook_delivery_success_total.labels(service=svc, job=JOB).inc(wh_success)

        time.sleep(1)   # update every second


# ══════════════════════════════════════════════════════════════════════════════
# HTTP server — Prometheus scrape endpoint
# ══════════════════════════════════════════════════════════════════════════════

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            output = generate_latest(REGISTRY)
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(output)
        elif self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass   # suppress access log noise


if __name__ == "__main__":
    print("Starting fake metrics exporter on :9999 ...")
    threading.Thread(target=update_metrics, daemon=True).start()
    server = HTTPServer(("0.0.0.0", 9999), MetricsHandler)
    print("Metrics available at http://localhost:9999/metrics")
    print("Incidents fire automatically every 90–180 seconds")
    server.serve_forever()
