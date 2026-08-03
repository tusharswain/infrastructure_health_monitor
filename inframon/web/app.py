"""Flask web UI and Prometheus /metrics endpoint."""
from __future__ import annotations

import os
from datetime import datetime
from urllib.parse import quote

from flask import Flask, Response, jsonify, render_template
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest

from inframon.config import Settings
from inframon.models import Alert, MetricSnapshot, Severity
from inframon.state import APP_STATE

_GAUGES: dict[str, Gauge] = {
    "cpu_percent": Gauge("infra_cpu_percent", "CPU utilisation percent", ["node"]),
    "memory_percent": Gauge("infra_memory_percent", "Memory utilisation percent", ["node"]),
    "disk_percent": Gauge("infra_disk_percent", "Disk utilisation percent", ["node"]),
    "load_1": Gauge("infra_load_1", "1-minute load average", ["node"]),
    "swap_percent": Gauge("infra_swap_percent", "Swap utilisation percent", ["node"]),
    "zombie_count": Gauge("infra_zombie_count", "Number of zombie processes", ["node"]),
}

_ALERT_COUNT = Gauge("infra_alert_count", "Number of active alerts", ["severity"])


def _worst_severity(alerts: list[Alert]) -> Severity:
    order = [Severity.OK, Severity.WARNING, Severity.CRITICAL, Severity.EMERGENCY]
    worst = Severity.OK
    for alert in alerts:
        if order.index(alert.severity) > order.index(worst):
            worst = alert.severity
    return worst


def _status_class(severity: Severity) -> str:
    if severity == Severity.OK:
        return "green"
    if severity == Severity.WARNING:
        return "yellow"
    return "red"


def create_app(settings: Settings) -> Flask:
    template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    static_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

    jenkins_url = settings.jenkins.url.rstrip("/") if settings.jenkins else None

    @app.route("/")
    def dashboard():
        snapshots = APP_STATE.snapshots()
        all_alerts = APP_STATE.alerts()
        node_data = []
        for name, snapshot in snapshots.items():
            node_alerts = [a for a in all_alerts if a.node == name]
            severity = _worst_severity(node_alerts)
            status, status_class = (severity.value, _status_class(severity))
            link = None
            if jenkins_url:
                link = f"{jenkins_url}/computer/{quote(name, safe='')}/"
            node_data.append(
                {
                    "name": name,
                    "status": status,
                    "status_class": status_class,
                    "snapshot": snapshot,
                    "link": link,
                }
            )
        return render_template("dashboard.html", nodes=node_data, alerts=all_alerts)

    @app.route("/api/status")
    def api_status():
        snapshots = {name: s.as_dict() for name, s in APP_STATE.snapshots().items()}
        alerts = [
            {
                "node": a.node,
                "metric": a.metric,
                "severity": a.severity.value,
                "value": a.value,
                "threshold": a.threshold,
                "message": a.message,
                "suggestions": a.suggestions,
                "actions": a.actions,
                "timestamp": a.timestamp.isoformat(),
            }
            for a in APP_STATE.alerts()
        ]
        return jsonify({"nodes": snapshots, "alerts": alerts})

    @app.route("/api/alerts")
    def api_alerts():
        alerts = APP_STATE.alerts()
        return jsonify(
            [
                {
                    "node": a.node,
                    "metric": a.metric,
                    "severity": a.severity.value,
                    "value": a.value,
                    "message": a.message,
                }
                for a in alerts
            ]
        )

    @app.route("/metrics")
    def metrics():
        snapshots = APP_STATE.snapshots()
        alerts = APP_STATE.alerts()

        # Clear old labels so removed nodes disappear.
        for gauge in _GAUGES.values():
            gauge.clear()

        for name, snapshot in snapshots.items():
            _GAUGES["cpu_percent"].labels(node=name).set(snapshot.cpu_percent)
            _GAUGES["memory_percent"].labels(node=name).set(snapshot.memory_percent)
            _GAUGES["disk_percent"].labels(node=name).set(snapshot.disk_percent)
            _GAUGES["load_1"].labels(node=name).set(snapshot.load_1)
            _GAUGES["swap_percent"].labels(node=name).set(snapshot.swap_percent)
            _GAUGES["zombie_count"].labels(node=name).set(snapshot.zombie_count)

        _ALERT_COUNT.clear()
        for severity in Severity:
            _ALERT_COUNT.labels(severity=severity.value).set(
                sum(1 for a in alerts if a.severity == severity)
            )

        return Response(
            generate_latest(),
            mimetype=CONTENT_TYPE_LATEST,
        )

    return app
