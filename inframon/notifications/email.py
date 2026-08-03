"""HTML email notifier with traffic-light status."""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote

from jinja2 import Environment, PackageLoader

from inframon.config import SMTPConfig
from inframon.models import Alert, MetricSnapshot, Severity

logger = logging.getLogger(__name__)

_ENV = Environment(loader=PackageLoader("inframon", "templates"))


def _node_status(snapshot: MetricSnapshot, alerts: list[Alert]) -> tuple[str, str]:
    worst = Severity.OK
    for alert in alerts:
        if alert.node == snapshot.node:
            if alert.severity == Severity.EMERGENCY:
                worst = Severity.EMERGENCY
            elif alert.severity == Severity.CRITICAL and worst != Severity.EMERGENCY:
                worst = Severity.CRITICAL
            elif alert.severity == Severity.WARNING and worst not in (Severity.EMERGENCY, Severity.CRITICAL):
                worst = Severity.WARNING

    mapping = {
        Severity.OK: ("OK", "green"),
        Severity.WARNING: ("WARNING", "yellow"),
        Severity.CRITICAL: ("CRITICAL", "red"),
        Severity.EMERGENCY: ("EMERGENCY", "red"),
    }
    return mapping[worst]


def _overall_status(alerts: list[Alert]) -> tuple[str, str]:
    if any(a.severity == Severity.EMERGENCY for a in alerts):
        return "EMERGENCY", "red"
    if any(a.severity == Severity.CRITICAL for a in alerts):
        return "CRITICAL", "red"
    if any(a.severity == Severity.WARNING for a in alerts):
        return "WARNING", "yellow"
    return "HEALTHY", "green"


class EmailNotifier:
    """Send formatted HTML email reports with traffic-light status."""

    def __init__(
        self,
        config: SMTPConfig,
        jenkins_url: str | None = None,
        on_severity: list[str] | None = None,
    ) -> None:
        self.config = config
        self.jenkins_url = jenkins_url.rstrip("/") if jenkins_url else None
        self.on_severity = set(on_severity or [s.value for s in Severity])

    def _jenkins_link(self, node_name: str) -> str | None:
        if not self.jenkins_url:
            return None
        return f"{self.jenkins_url}/computer/{quote(node_name, safe='')}/"

    def send(self, snapshots: list[MetricSnapshot], alerts: list[Alert]) -> None:
        alerts = [a for a in alerts if a.severity.value in self.on_severity]
        if not alerts:
            return

        template = _ENV.get_template("email_report.html")
        overall, overall_class = _overall_status(alerts)

        nodes = []
        for snapshot in snapshots:
            node_alerts = [a for a in alerts if a.node == snapshot.node]
            status, status_class = _node_status(snapshot, node_alerts)
            nodes.append(
                {
                    "name": snapshot.node,
                    "status": status,
                    "status_class": status_class,
                    "cpu": f"{snapshot.cpu_percent:.1f}",
                    "mem": f"{snapshot.memory_percent:.1f}",
                    "disk": f"{snapshot.disk_percent:.1f}",
                    "load": f"{snapshot.load_1:.2f}",
                    "swap": f"{snapshot.swap_percent:.1f}",
                    "zombies": snapshot.zombie_count,
                    "link": self._jenkins_link(snapshot.node),
                }
            )

        alert_rows = [
            {
                "node": a.node,
                "severity": a.severity.value,
                "status_class": "red" if a.severity in (Severity.CRITICAL, Severity.EMERGENCY) else "yellow",
                "metric": a.metric,
                "value": f"{a.value:.2f}",
                "threshold": f"{a.threshold:.2f}" if a.threshold else "-",
                "message": a.message,
                "suggestions": a.suggestions,
                "actions": a.actions,
            }
            for a in alerts
        ]

        html = template.render(
            overall_status=overall,
            overall_class=overall_class,
            nodes=nodes,
            alerts=alert_rows,
        )

        plain = self._plain_text(nodes, alert_rows)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[Infrastructure Health] {overall}"
        msg["From"] = self.config.from_addr
        msg["To"] = ", ".join(self.config.to_addrs)

        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html, "html"))

        try:
            with smtplib.SMTP(self.config.host, self.config.port) as server:
                if self.config.use_tls:
                    server.starttls()
                server.login(self.config.user, self.config.password)
                server.sendmail(self.config.from_addr, self.config.to_addrs, msg.as_string())
            logger.info("Email sent to %s", self.config.to_addrs)
        except Exception as exc:
            logger.exception("Failed to send email: %s", exc)

    def _plain_text(self, nodes: list[dict], alerts: list[dict]) -> str:
        lines = ["Infrastructure Health Report", ""]
        lines.append(f"Overall: {nodes[0]['status'] if nodes else 'N/A'}")
        lines.append("")
        lines.append("Nodes:")
        for n in nodes:
            lines.append(f"- {n['name']}: {n['status']} CPU={n['cpu']}% MEM={n['mem']}% DISK={n['disk']}% LOAD={n['load']}")
        if alerts:
            lines.append("")
            lines.append("Alerts:")
            for a in alerts:
                lines.append(f"- [{a['severity']}] {a['node']} {a['metric']}={a['value']} ({a['message']})")
        return "\n".join(lines)
