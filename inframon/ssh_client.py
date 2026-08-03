"""Shared SSH helper for the monitor."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import paramiko

from inframon.config import Node


@contextmanager
def ssh_client(node: Node, timeout: int = 20):
    """Yield a connected Paramiko SSHClient for a node."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    kwargs: dict = {
        "hostname": node.host,
        "port": node.ssh_port,
        "username": node.ssh_user,
        "timeout": timeout,
        "allow_agent": True,
        "look_for_keys": True,
    }
    if node.ssh_key:
        kwargs["key_filename"] = str(Path(node.ssh_key).expanduser())
    if node.ssh_password:
        kwargs["password"] = node.ssh_password

    try:
        client.connect(**kwargs)
        yield client
    finally:
        client.close()


def run_command(node: Node, command: str, timeout: int = 20) -> str:
    """Run a command on a remote node and return stdout."""
    with ssh_client(node, timeout=timeout) as client:
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        stdout.channel.set_combine_stderr(True)
        output = stdout.read().decode("utf-8", errors="replace")
        exit_code = stdout.channel.recv_exit_status()
        if exit_code != 0:
            raise RuntimeError(f"SSH command failed with exit {exit_code}: {output.strip()}")
        return output
