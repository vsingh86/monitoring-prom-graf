# Implementation guide: exposing host metrics

For the **server/infrastructure team** — this covers installing and
exposing OS-level metrics (CPU, memory, disk, network) on a
self-hosted Linux or Windows server so it shows up on the monitoring
platform's Infrastructure layer. If the application in question runs on
vendor-managed infrastructure you can't install anything on (managed
PaaS, vendor-hosted), this doesn't apply .

This is the detailed how-to behind
[`onboarding-consumer-app.md`](onboarding-consumer-app.md) step 2. Jump
to your OS: [Linux](#linux-node_exporter) · [Windows](#windows-windows_exporter)

**Why the exact collector set matters:** the platform's recording rules
(`prometheus/rules/data-mapping/infra_linux.yml` /
`infra_windows.yml`) normalize specific exporter metric names into a
shared `host:*` schema every dashboard queries. Both exporters' *default*
collector sets already produce everything needed — you generally don't
need to change exporter flags, just install it, expose port, and get the
scrape job wired up correctly (`host_type` label). The instructions below
call out the few places a non-default setup would cause "No data."

---

## Linux (`node_exporter`)

**Exporter:** [`node_exporter`](https://github.com/prometheus/node_exporter)
**Default port:** `9100`, path `/metrics`
**`host_type` label:** `linux`
**Recording rule:** [`prometheus/rules/data-mapping/infra_linux.yml`](../prometheus/rules/data-mapping/infra_linux.yml)

### Install

```bash
# Download the latest release for your architecture from
# https://github.com/prometheus/node_exporter/releases
VERSION=1.8.2
curl -LO https://github.com/prometheus/node_exporter/releases/download/v${VERSION}/node_exporter-${VERSION}.linux-amd64.tar.gz
tar xzf node_exporter-${VERSION}.linux-amd64.tar.gz
sudo mv node_exporter-${VERSION}.linux-amd64/node_exporter /usr/local/bin/
sudo useradd --no-create-home --shell /usr/sbin/nologin node_exporter
```

Run it as a systemd service rather than manually so it survives reboots:

```ini
# /etc/systemd/system/node_exporter.service
[Unit]
Description=Prometheus Node Exporter
After=network.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now node_exporter
```

Default collectors (cpu, meminfo, diskstats, filesystem, netdev, loadavg,
and others) are exactly what `infra_linux.yml` expects — **don't disable
any of these** with `--no-collector.<name>` unless you have a specific
reason, since that would show up as "No data" on the corresponding
dashboard panel with no obvious error anywhere.

### Verify

```bash
curl http://localhost:9100/metrics | grep -E '^node_cpu_seconds_total|^node_memory_MemAvailable_bytes'
```
Both should return non-empty output.

---

## Windows (`windows_exporter`)

**Exporter:** [`windows_exporter`](https://github.com/prometheus-community/windows_exporter)
**Default port:** `9182`, path `/metrics`
**`host_type` label:** `windows`
**Recording rule:** [`prometheus/rules/data-mapping/infra_windows.yml`](../prometheus/rules/data-mapping/infra_windows.yml)

### Install

Download the MSI installer from the
[releases page](https://github.com/prometheus-community/windows_exporter/releases)
and run it, **or** install via the command line specifying the exact
collector set the recording rule expects:

```powershell
msiexec /i windows_exporter-<version>-amd64.msi ENABLED_COLLECTORS="cpu,cs,logical_disk,memory,net,os"
```

**This platform's `infra_windows.yml` recording rule specifically assumes
these six default collectors are enabled: `cpu`, `cs`, `logical_disk`,
`memory`, `net`, `os`.** These happen to be windows_exporter's default
set, so a plain default install already works — but if your org's base
image customizes `ENABLED_COLLECTORS`, explicitly confirm these six are
still in it. It installs and runs as a Windows service
(`windows_exporter`) automatically — no separate service-registration
step needed like on Linux.

### Verify

```powershell
Invoke-WebRequest http://localhost:9182/metrics | Select-String "windows_cpu_time_total|windows_memory_available_bytes"
```
Both should return output.

---

## Securing the endpoint (both OSes)

`/metrics` exposes host-level detail (running processes' resource usage
indirectly, network interface info, mount points) — treat it like any
other internal service, not something to leave open to the internet:

- **Firewall/security group:** restrict inbound access on the exporter's
  port (9100 Linux / 9182 Windows) to only the Prometheus server's IP —
  don't leave it open to the whole network.
- **TLS + basic auth (recommended if reachable beyond a fully private
  network):** both exporters support the same
  [`exporter-toolkit` web config format](https://github.com/prometheus/exporter-toolkit/blob/master/docs/web-configuration.md)
  via a `--web.config.file` flag — this platform already runs at least
  one Windows host this way (TLS + a basic-auth username/password pair).
  Example `web-config.yml`:
  ```yaml
  basic_auth_users:
    admin: $2y$10$<bcrypt-hash-of-your-password>   # generate with htpasswd -nBC 10 admin
  tls_server_config:
    cert_file: server.crt
    key_file: server.key
  ```
  Linux: `node_exporter --web.config.file=web-config.yml`
  Windows: add `--web.config.file="C:\path\web-config.yml"` to the
  service's start parameters (via `sc.exe config windows_exporter
  binPath= "... --web.config.file=..."` or re-run the MSI with the flag).
  If you set this up, the platform team's scrape job will need
  `scheme: https` and `basic_auth: {username, password}` (or a bearer
  token if you front it differently) — tell them which when you hand off.

## What to hand back to the platform team

Once the exporter is installed, reachable, and verified, give the app
team (who pass it to the platform team per
[`onboarding-new-app.md`](onboarding-new-app.md) step 4):

- **Host address:port** — e.g. `my-app-host.example.com:9100` (Linux) or
  `:9182` (Windows).
- **OS type** — Linux or Windows (becomes the `host_type` label).
- **Auth method**, if you set up TLS/basic auth above — scheme, username,
  and where the password lives (a secret, not chat/email) — or
  confirmation there's none (acceptable only on a fully private network
  reachable solely by the Prometheus server).
- **Which app(s) this host serves** — if the host is dedicated to one
  application, the platform team labels it `app: <Name>`. **If the host
  is shared across multiple applications, say so explicitly** — the
  platform team will deliberately leave `app` off that job, so the
  dashboard doesn't misattribute a shared host's resource usage to one
  app's view.
