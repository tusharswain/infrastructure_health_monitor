"""Remediation orchestrator that maps alerts to safe actions."""
from __future__ import annotations

import logging

from inframon.config import Node, RemediationConfig
from inframon.jenkins.client import JenkinsClient
from inframon.models import Alert, RemediationLog, Severity
from inframon.remediation.actions import ActionRegistry

logger = logging.getLogger(__name__)


class RemediationEngine:
    """Decide and execute remediation actions for a given alert."""

    def __init__(
        self,
        config: RemediationConfig,
        jenkins_client: JenkinsClient | None = None,
    ) -> None:
        self.config = config
        self.actions = ActionRegistry(config, jenkins_client=jenkins_client)
        self.logs: list[RemediationLog] = []
        self._marked_offline: set[str] = set()

    @property
    def marked_offline(self) -> set[str]:
        return set(self._marked_offline)

    def handle(self, alert: Alert, node: Node) -> None:
        if not self.config.enabled:
            logger.info("Remediation disabled; would have handled %s on %s", alert.metric, node.name)
            return

        planned = self._plan_actions(alert, node)
        for action_name, kwargs in planned:
            success, message = self._execute_action(action_name, node, alert, kwargs)
            log = RemediationLog(
                node=node.name,
                action=action_name,
                severity=alert.severity,
                dry_run=self.config.dry_run,
                success=success,
                message=message,
            )
            self.logs.append(log)
            alert.actions.append(message)
            logger.info("Remediation: %s", message)

    def _plan_actions(self, alert: Alert, node: Node) -> list[tuple[str, dict]]:
        """Return a list of (action_name, kwargs) based on severity."""
        actions: list[tuple[str, dict]] = []

        # Take Jenkins offline for CRITICAL/EMERGENCY to protect builds
        if self.actions.jenkins and alert.severity in (Severity.CRITICAL, Severity.EMERGENCY):
            actions.append(("mark_jenkins_offline", {"reason": alert.message}))

        # Restart safe services for EMERGENCY only, unless configured otherwise
        if alert.severity == Severity.EMERGENCY:
            for service in node.services:
                if service in self.config.whitelist:
                    actions.append(("restart_service", {"service": service}))

        return actions

    def _execute_action(
        self, action_name: str, node: Node, alert: Alert, kwargs: dict
    ) -> tuple[bool, str]:
        if action_name == "mark_jenkins_offline":
            success, message = self.actions.mark_jenkins_offline(
                node, kwargs.get("reason", alert.message)
            )
            if success:
                self._marked_offline.add(node.name)
            return success, message
        if action_name == "restart_service":
            return self.actions.restart_service(node, kwargs["service"])
        if action_name == "cancel_jenkins_offline":
            success, message = self.actions.cancel_jenkins_offline(node)
            if success:
                self._marked_offline.discard(node.name)
            return success, message
        return False, f"Unknown action {action_name}"

    def recover(self, node: Node) -> None:
        """Cancel Jenkins offline status for nodes we previously marked offline."""
        if not self.config.enabled:
            return
        if node.name not in self._marked_offline:
            return
        success, message = self.actions.cancel_jenkins_offline(node)
        if success:
            self._marked_offline.discard(node.name)
            logger.info("Recovery: %s", message)
