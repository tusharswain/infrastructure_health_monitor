# Infrastructure Health Monitor with Auto-Remediation Engine

[![CI](https://github.com/tusharswain/infrastructure_health_monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/tusharswain/infrastructure_health_monitor/actions/workflows/ci.yml)

A Python service that continuously monitors **Jenkins nodes, Linux VMs, bare-metal servers, and Kubernetes pods**, detects sustained health issues, classifies severity, auto-remediates safe problems, and sends rich notifications and daily trend reports.

It demonstrates: API integration (Jenkins), auto-remediation, trend analysis, sliding-window alerting, pluggable storage, and a live web UI with Prometheus metrics.

---

## What it monitors

- **CPU utilisation**
- **Memory utilisation**
- **Disk utilisation**
- **1/5/15-minute load average**
- **Swap usage**
- **Zombie processes**
- **Network in/out bytes/sec** (for Linux/SSH targets)

---

## Key features

| Feature | Implementation |
|---|---|
| Multi-target monitoring | Local, SSH, and Kubernetes pod collectors |
| Jenkins API integration | Dynamic node list, mark nodes offline/online |
| Sustained alerting | Sliding-window threshold engine with retry logic |
| Severity levels | `WARNING`, `CRITICAL`, `EMERGENCY` |
| Auto-remediation | Mark Jenkins offline + restart whitelisted services |
| Specific fix suggestions | Context-aware hints per metric and severity |
| Notifications | Formatted HTML email with traffic-light status |
| Historical storage | CSV by default, InfluxDB optional |
| Trend reports | Daily HTML/PDF charts with `matplotlib` |
| Web UI + Prometheus | Flask dashboard and `/metrics` endpoint |
| Docker stack | Dockerfile + `docker-compose.yml` with Prometheus & Grafana |

---

## Project structure

```text
infrastructure_health_monitor/
├── config/
│   ├── settings.yaml               # thresholds, intervals, storage, web
│   ├── nodes.yaml                  # nodes/pods to monitor
│   └── credentials.yaml.example    # copy to credentials.yaml and fill secrets
├── inframon/
│   ├── config.py                   # Pydantic settings loader
│   ├── models.py                   # Alert, MetricSnapshot, Severity
│   ├── state.py                    # thread-safe live state
│   ├── collector/                  # local, SSH, k8s metric collectors
│   ├── jenkins/                    # Jenkins REST API client
│   ├── engine/                     # threshold + sliding window logic
│   ├── remediation/                # safe auto-remediation engine
│   ├── notifications/              # HTML email notifier
│   ├── storage/                    # CSV / InfluxDB stores
│   ├── reporter/                   # daily HTML/PDF reports
│   ├── web/                        # Flask dashboard + /metrics
│   └── templates/                  # Jinja2 templates
├── tests/                          # pytest suite
├── Dockerfile
├── docker-compose.yml
├── prometheus.yml
├── requirements.txt
├── pyproject.toml
└── run.py                          # CLI entry point
```

---

## Quick start

### 1. Create a virtual environment and install dependencies

```bash
cd infrastructure_health_monitor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp config/credentials.yaml.example config/credentials.yaml
```

Edit `config/credentials.yaml` with your Jenkins API token and SMTP password. It is already gitignored.

### 3. Configure nodes

Edit `config/nodes.yaml` to match your environment. Example:

```yaml
nodes:
  - name: local
    host: localhost
    type: local

  - name: jenkins-build-01
    host: 10.0.0.11
    type: ssh
    ssh_user: jenkins
    ssh_key: ~/.ssh/id_rsa
    jenkins_node_name: jenkins-build-01  # name in Jenkins if different
    tags: [jenkins]
    services: [jenkins, docker]
    allow_restart: false
```

### 4. Run a one-shot check

```bash
python run.py check
```

### 5. Start continuous monitoring with the web UI

Set `web.enabled: true` in `config/settings.yaml`, then:

```bash
python run.py monitor
```

Open:

- Dashboard: `http://localhost:5000/`
- Prometheus metrics: `http://localhost:5000/metrics`
- JSON status: `http://localhost:5000/api/status`

---

## CLI commands

| Command | Purpose |
|---|---|
| `python run.py check --node NODE` | One-shot health check |
| `python run.py monitor --interval 60` | Continuous monitoring |
| `python run.py web --port 5000` | Start only the Flask UI |
| `python run.py report --date 2026-07-27` | Generate daily report |
| `python run.py reset-node NODE` | Mark Jenkins node online |

---

## Configuration

`config/settings.yaml` contains:

- `interval`: seconds between monitoring cycles
- `thresholds`: per-metric warning/critical/emergency thresholds
- `window_size` / `window_type`: how many samples and whether to use `consecutive` or `average` for sustained breach detection
- `remediation`: enable/disable, dry-run, restart whitelist, daily restart limits
- `storage`: `csv` or `influxdb`
- `notifications.email.on_severity`: which severities trigger email
- `web`: Flask UI settings

You can also override secrets via environment variables:

- `JENKINS_URL`
- `JENKINS_USER`
- `JENKINS_TOKEN`
- `SMTP_PASSWORD`

---

## Alert severity and actions

| Severity | Meaning | Action |
|---|---|---|
| **WARNING** | Trending toward a problem | Email + specific fix suggestions |
| **CRITICAL** | Problem confirmed | Email + mark Jenkins node offline |
| **EMERGENCY** | Immediate risk | Email + offline + restart whitelisted services |

Remediation starts in **dry-run mode** by default. Set `remediation.dry_run: false` to enable real actions.

---

## Prometheus + Grafana (optional)

A full Docker Compose stack is included:

```bash
# Default app host port is 5001 to avoid macOS ControlCenter/AirPlay on 5000
docker compose up -d

# Or choose a different host port
APP_PORT=5002 docker compose up -d
```

Services:

- App: `http://localhost:5001` (or `${APP_PORT}`)
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (admin/admin)
- InfluxDB: `http://localhost:8086`

> **macOS note:** On macOS Monterey+, port `5000` is used by Control Center / AirPlay Receiver. The compose file now defaults to `5001` to avoid this. You can disable AirPlay Receiver (`System Settings -> General -> AirDrop & Handoff`) if you must use `5000`.

Prometheus scrapes the app at `/metrics`. Grafana is auto-provisioned with an **Infrastructure Health** dashboard showing CPU, memory, disk, load, swap, zombies, and active alert counts per node.

---

## Daily trend reports

Historical metrics are stored in `data/metrics/` by default. Generate a report:

```bash
python run.py report
python run.py report --date 2026-07-27 --format pdf
```

Reports are saved to `reports/`.

---

## Tests

```bash
pytest -q
```

---

## Testing Jenkins integration in a container

You do not need a host Jenkins install. A Jenkins controller is included as an optional Docker Compose profile.

### 1. Start the Jenkins container

```bash
docker compose --profile jenkins up -d
```

Jenkins will be available at `http://localhost:8080`.

### 2. Complete the Jenkins setup

Get the initial admin password:

```bash
docker compose logs jenkins | grep "password for the user"
```

Open `http://localhost:8080`, install the suggested plugins, create an admin user, and generate an API token for that user (`/user/<username>/configure`).

### 3. Configure credentials for the test stack

```bash
cp config/credentials.yaml.example config/credentials.yaml
```

Fill in `config/credentials.yaml`:

```yaml
jenkins:
  token: your-generated-api-token
```

### 4. Test the Jenkins API from the CLI

```bash
# List Jenkins nodes
python run.py --config config/settings.test.yaml reset-node "Built-In Node"
```

If the node is offline, this marks it online; if it is online, nothing changes.

To trigger a Jenkins offline action, lower the thresholds in `config/settings.test.yaml` and run:

```bash
python run.py --config config/settings.test.yaml check
```

The test settings use `config/nodes.test.yaml`, where the monitored `jenkins-test-node` maps to the Jenkins node `Built-In Node` via the `jenkins_node_name` field.

### Notes

- `jenkins_node_name` lets the monitor map any monitored node (`name`) to a different Jenkins node name.
- The `jenkins` service is in the `jenkins` profile, so it does not start unless you explicitly request it (`--profile jenkins`).
- For a production Jenkins, set `verify_ssl: true` and store the token in `config/credentials.yaml`.

---

## Security notes

- `config/credentials.yaml` is gitignored.
- Remediation is **dry-run** by default.
- Service restarts require `allow_restart: true` on the node **and** the service in the global `whitelist`.
- SSH authentication uses keys or passwords from config, never hardcoded.
