"""Remediation actions executed by the monitor."""
from __future__ import annotations

import logging
import subprocess
from datetime import date

from inframon.config import Node, RemediationConfig
from inframon.jenkins.client import JenkinsClient
from inframon.ssh_client import run_command

logger = logging.getLogger(__name__)


class ActionRegistry:
    """Executes remediation actions with dry-run support and safety checks."""

    def __init__(
        self,
        config: RemediationConfig,
        jenkins_client: JenkinsClient | None = None,
    ) -> None:
        self.config = config
        self.jenkins = jenkins_client
        self.daily_restart_counts: dict[str, int] = {}
        self.today = date.today()

    def _refresh_day(self) -> None:
        today = date.today()
        if today != self.today:
            self.today = today
            self.daily_restart_counts = {}

    def _jenkins_name(self, node: Node) -> str:
        return node.jenkins_node_name or node.name

    def mark_jenkins_offline(self, node: Node, reason: str) -> tuple[bool, str]:
        if not self.jenkins:
            return False, "Jenkins not configured"
        jenkins_name = self._jenkins_name(node)
        if self.config.dry_run:
            return True, f"[DRY-RUN] Would mark {jenkins_name} ({node.name}) offline in Jenkins"
        try:
            self.jenkins.mark_offline(jenkins_name, reason)
            return True, f"Marked {jenkins_name} offline in Jenkins"
        except Exception as exc:
            logger.exception("Failed to mark %s offline", jenkins_name)
            return False, f"Failed to mark {jenkins_name} offline: {exc}"

    def restart_service(self, node: Node, service: str) -> tuple[bool, str]:
        self._refresh_day()

        if not node.allow_restart:
            return False, f"Restart not allowed for {node.name}"
        if service not in self.config.whitelist:
            return False, f"Service {service} is not in the global remediation whitelist"
        if node.services and service not in node.services:
            return False, f"Service {service} is not listed for node {node.name}"

        count_key = f"{node.name}:{service}"
        if self.daily_restart_counts.get(count_key, 0) >= self.config.max_daily_restarts:
            return False, f"Daily restart limit reached for {service} on {node.name}"

        if self.config.dry_run:
            return True, f"[DRY-RUN] Would restart {service} on {node.name}"

        command = f"sudo systemctl restart {service}"
        try:
            if node.type == "local":
                subprocess.run(
                    command,
                    shell=True,
                    check=True,
                    timeout=30,
                    capture_output=True,
                    text=True,
                )
            else:
                run_command(node, command, timeout=30)
            self.daily_restart_counts[count_key] = self.daily_restart_counts.get(count_key, 0) + 1
            return True, f"Restarted {service} on {node.name}"
        except Exception as exc:
            logger.exception("Failed to restart %s on %s", service, node.name)
            return False, f"Failed to restart {service} on {node.name}: {exc}"

    def cancel_jenkins_offline(self, node: Node) -> tuple[bool, str]:
        if not self.jenkins:
            return False, "Jenkins not configured"
        jenkins_name = self._jenkins_name(node)
        if self.config.dry_run:
            return True, f"[DRY-RUN] Would mark {jenkins_name} ({node.name}) online in Jenkins"
        try:
            self.jenkins.mark_online(jenkins_name)
            return True, f"Marked {jenkins_name} online in Jenkins"
        except Exception as exc:
            logger.exception("Failed to mark %s online", jenkins_name)
            return False, f"Failed to mark {jenkins_name} online: {exc}"
