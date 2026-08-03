"""Kubernetes pod metric collector using kubectl exec / kubectl top."""
from __future__ import annotations

import logging
import re
import subprocess

from inframon.collector.base import BaseCollector
from inframon.collector.commands import parse_remote_output, remote_metric_command
from inframon.config import Node
from inframon.models import MetricSnapshot

logger = logging.getLogger(__name__)


class K8sCollector(BaseCollector):
    """Collect metrics from a Kubernetes pod.

    Tries `kubectl exec` first. If the pod has no shell, falls back to
    `kubectl top pod` for CPU/memory only.
    """

    def collect(self, node: Node) -> MetricSnapshot:
        if not node.pod_name or not node.namespace:
            raise ValueError(f"pod_name and namespace required for k8s node {node.name}")

        try:
            return self._exec_collect(node)
        except Exception as exc:
            logger.warning("kubectl exec failed for %s: %s; trying kubectl top", node.name, exc)
            return self._top_collect(node)

    def _exec_collect(self, node: Node) -> MetricSnapshot:
        cmd = ["kubectl", "exec", node.pod_name, "-n", node.namespace, "--", "sh", "-c", remote_metric_command()]
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=25)
        return parse_remote_output(node.name, output)

    def _top_collect(self, node: Node) -> MetricSnapshot:
        cmd = ["kubectl", "top", "pod", node.pod_name, "-n", node.namespace, "--no-headers"]
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=15)
        return self._parse_top(output, node.name)

    def _parse_top(self, output: str, node: Node) -> MetricSnapshot:
        parts = output.strip().split()
        if len(parts) >= 3:
            cpu_str = parts[1]
            mem_str = parts[2]
            cpu = self._parse_cpu_str(cpu_str)
            mem = self._parse_mem_str(mem_str)
            return self._snapshot(
                node,
                cpu_percent=cpu,
                memory_percent=mem,
            )
        return self._snapshot(node)

    @staticmethod
    def _parse_cpu_str(value: str) -> float:
        match = re.match(r"([\d.]+)(m?)", value)
        if not match:
            return 0.0
        num = float(match.group(1))
        if match.group(2) == "m":
            # Millicores; rough percent assuming 1 core requested if unknown
            return num / 10.0
        return num

    @staticmethod
    def _parse_mem_str(value: str) -> float:
        match = re.match(r"([\d.]+)([KMGT]?i?)", value)
        if not match:
            return 0.0
        num = float(match.group(1))
        unit = match.group(2).upper()
        # Rough Mi conversion
        multipliers = {"": 1, "K": 1 / 1024, "M": 1, "G": 1024, "T": 1024 * 1024}
        if unit == "":
            unit = "M"
        return num * multipliers.get(unit, 1)
