"""SSH metric collector using Paramiko."""
from __future__ import annotations

import logging
from pathlib import Path

import paramiko

from inframon.collector.base import BaseCollector
from inframon.collector.commands import parse_remote_output, remote_metric_command
from inframon.config import Node
from inframon.models import MetricSnapshot

logger = logging.getLogger(__name__)


class SSHCollector(BaseCollector):
    """Collect metrics from a Linux node over SSH."""

    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout

    def collect(self, node: Node) -> MetricSnapshot:
        if not node.ssh_user:
            raise ValueError(f"SSH user not configured for node {node.name}")

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        kwargs: dict = {
            "hostname": node.host,
            "port": node.ssh_port,
            "username": node.ssh_user,
            "timeout": self.timeout,
            "allow_agent": True,
            "look_for_keys": True,
        }

        if node.ssh_key:
            key_path = Path(node.ssh_key).expanduser()
            kwargs["key_filename"] = str(key_path)
        if node.ssh_password:
            kwargs["password"] = node.ssh_password

        try:
            client.connect(**kwargs)
            cmd = remote_metric_command()
            stdin, stdout, stderr = client.exec_command(cmd, timeout=self.timeout)
            stdout.channel.set_combine_stderr(True)
            output = stdout.read().decode("utf-8", errors="replace")
            exit_code = stdout.channel.recv_exit_status()
            if exit_code != 0:
                err = stderr.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"SSH command failed with {exit_code}: {err}")
            return parse_remote_output(node.name, output)
        finally:
            client.close()
