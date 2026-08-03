"""Tests for the remediation engine."""
from __future__ import annotations

from inframon.config import Node, RemediationConfig
from inframon.models import Alert, MetricSnapshot, Severity
from inframon.remediation.engine import RemediationEngine


def test_dry_run_does_not_execute_restart():
    config = RemediationConfig(enabled=True, dry_run=True, whitelist=["jenkins"])
    engine = RemediationEngine(config, jenkins_client=None)
    node = Node(
        name="worker",
        host="10.0.0.1",
        type="ssh",
        services=["jenkins"],
        allow_restart=True,
    )
    alert = Alert(
        node="worker",
        metric="cpu_percent",
        severity=Severity.EMERGENCY,
        value=96,
        threshold=95,
        message="CPU critical",
        suggestions=[],
    )
    engine.handle(alert, node)

    assert len(alert.actions) == 1
    assert "[DRY-RUN]" in alert.actions[0]


def test_marked_offline_tracking():
    config = RemediationConfig(enabled=True, dry_run=True, whitelist=[])
    engine = RemediationEngine(config, jenkins_client=None)
    node = Node(name="worker", host="10.0.0.1", type="ssh")
    assert "worker" not in engine.marked_offline
