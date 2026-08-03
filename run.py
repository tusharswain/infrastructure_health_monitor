#!/usr/bin/env python3
"""CLI entry point for the Infrastructure Health Monitor."""
from __future__ import annotations

import logging
import sys
import threading
import time
from datetime import datetime, timezone

import click

from inframon.collector import get_collector
from inframon.config import load_settings
from inframon.engine.evaluator import ThresholdEvaluator
from inframon.jenkins.client import JenkinsClient
from inframon.notifications.email import EmailNotifier
from inframon.remediation.engine import RemediationEngine
from inframon.reporter.daily_report import DailyReport
from inframon.state import APP_STATE
from inframon.storage.csv_store import CSVStore
from inframon.storage.influx_store import InfluxDBStore
from inframon.web.app import create_app


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _store_for(settings):
    if settings.storage.type == "influxdb":
        return InfluxDBStore(settings.storage)
    return CSVStore(settings.storage)


def _jenkins_url(settings):
    return settings.jenkins.url if settings.jenkins else None


def _notifier_for(settings):
    if not settings.smtp:
        return None
    email_cfg = settings.notifications.get("email", {})
    if not email_cfg.get("enabled", True):
        return None
    return EmailNotifier(
        settings.smtp,
        jenkins_url=_jenkins_url(settings),
        on_severity=email_cfg.get("on_severity"),
    )


@click.group()
@click.option("--config", "-c", default="config/settings.yaml", help="Path to settings YAML")
@click.pass_context
def cli(ctx, config: str):
    """Infrastructure Health Monitor with Auto-Remediation."""
    ctx.ensure_object(dict)
    settings = load_settings(config)
    ctx.obj["settings"] = settings
    _setup_logging(settings.log_level)


@cli.command()
@click.option("--node", help="Check a single node; otherwise all nodes")
@click.pass_context
def check(ctx, node: str | None):
    """Run a one-shot health check."""
    settings = ctx.obj["settings"]
    nodes = [n for n in settings.nodes if node is None or n.name == node]
    if not nodes:
        click.echo(f"Node {node!r} not found", err=True)
        sys.exit(1)

    store = _store_for(settings)
    evaluator = ThresholdEvaluator(settings.thresholds)
    jenkins = JenkinsClient(settings.jenkins) if settings.jenkins else None
    notifier = _notifier_for(settings)
    remediation = RemediationEngine(settings.remediation, jenkins_client=jenkins)

    all_snapshots = []
    all_alerts = []
    for n in nodes:
        collector = get_collector(n.type)
        try:
            snapshot = collector.collect(n)
        except Exception as exc:
            logging.getLogger(__name__).error("Failed to collect from %s: %s", n.name, exc)
            continue

        APP_STATE.update(n.name, snapshot)
        store.save(snapshot)
        all_snapshots.append(snapshot)

        APP_STATE.clear_alerts(n.name)
        alerts = evaluator.evaluate(snapshot)
        for alert in alerts:
            logging.getLogger(__name__).warning("%s", alert)
            APP_STATE.add_alert(alert)
            remediation.handle(alert, n)
        all_alerts.extend(alerts)

    if notifier and all_alerts:
        notifier.send(all_snapshots, all_alerts)


@cli.command()
@click.option("--interval", type=int, help="Override monitoring interval in seconds")
@click.pass_context
def monitor(ctx, interval: int | None):
    """Continuously monitor nodes and auto-remediate."""
    settings = ctx.obj["settings"]
    interval = interval or settings.interval
    store = _store_for(settings)
    evaluator = ThresholdEvaluator(settings.thresholds)
    jenkins = JenkinsClient(settings.jenkins) if settings.jenkins else None
    notifier = _notifier_for(settings)
    remediation = RemediationEngine(settings.remediation, jenkins_client=jenkins)

    if settings.web.enabled:
        app = create_app(settings)
        host = settings.web.host
        port = settings.web.port
        threading.Thread(
            target=app.run,
            kwargs={
                "host": host,
                "port": port,
                "threaded": True,
                "use_reloader": False,
                "debug": False,
            },
            daemon=True,
        ).start()
        click.echo(f"Web UI available at http://{host}:{port}")

    logging.getLogger(__name__).info("Starting monitor (interval=%ss)", interval)
    while True:
        all_snapshots = []
        all_alerts = []
        for n in settings.nodes:
            collector = get_collector(n.type)
            try:
                snapshot = collector.collect(n)
            except Exception as exc:
                logging.getLogger(__name__).error("Failed to collect from %s: %s", n.name, exc)
                continue

            APP_STATE.update(n.name, snapshot)
            store.save(snapshot)
            all_snapshots.append(snapshot)

            APP_STATE.clear_alerts(n.name)
            alerts = evaluator.evaluate(snapshot)
            node_has_alerts = bool(alerts)
            for alert in alerts:
                logging.getLogger(__name__).warning("%s", alert)
                APP_STATE.add_alert(alert)
                remediation.handle(alert, n)
            all_alerts.extend(alerts)

            # Auto-recover Jenkins offline when node is healthy again
            if not node_has_alerts:
                remediation.recover(n)

        if notifier and all_alerts:
            notifier.send(all_snapshots, all_alerts)

        time.sleep(interval)


@cli.command()
@click.option("--date", default=None, help="Date for report (YYYY-MM-DD); defaults to today")
@click.option("--format", "fmt", default="html", type=click.Choice(["html", "pdf"]))
@click.pass_context
def report(ctx, date: str | None, fmt: str):
    """Generate a daily health trend report."""
    settings = ctx.obj["settings"]
    target_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    reporter = DailyReport(settings.storage, output_dir="reports")
    path = reporter.generate(target_date, fmt=fmt)
    click.echo(f"Report generated: {path}")


@cli.command()
@click.option("--port", type=int, help="Override web UI port")
@click.pass_context
def web(ctx, port: int | None):
    """Start the Flask web UI and Prometheus metrics endpoint."""
    settings = ctx.obj["settings"]
    app = create_app(settings)
    host = settings.web.host
    port = port or settings.web.port
    click.echo(f"Starting web UI on http://{host}:{port}")
    app.run(host=host, port=port, threaded=True, use_reloader=False)


@cli.command()
@click.argument("node")
@click.pass_context
def reset_node(ctx, node: str):
    """Mark a Jenkins node online again."""
    settings = ctx.obj["settings"]
    if not settings.jenkins:
        click.echo("Jenkins not configured", err=True)
        sys.exit(1)
    jenkins = JenkinsClient(settings.jenkins)
    jenkins.mark_online(node)
    click.echo(f"Marked {node} online")


if __name__ == "__main__":
    cli()
