"""Shell command and parser for Linux SSH / k8s metric collection."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from inframon.models import MetricSnapshot


def remote_metric_command() -> str:
    return (
        "echo '===CPU==='; "
        "top -bn2 -d0.5 | grep '%Cpu(s)' | tail -n 1; "
        "echo '===MEM==='; free; "
        "echo '===DISK==='; df -P /; "
        "echo '===LOAD==='; uptime; "
        "echo '===ZOMBIE==='; ps aux | awk '$8 ~ /Z/' | wc -l; "
        "echo '===NET1==='; cat /proc/net/dev; "
        "echo '===NET2==='; sleep 1; cat /proc/net/dev"
    )


def _section(lines: list[str], marker: str) -> list[str]:
    capture = False
    section_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped == f"==={marker}===":
            capture = True
            continue
        if stripped.startswith("===") and stripped.endswith("===") and capture:
            break
        if capture:
            section_lines.append(line)
    return section_lines


def _parse_cpu(lines: list[str]) -> float:
    for line in lines:
        match = re.search(r"([\d.]+)\s*id,?", line)
        if match:
            idle = float(match.group(1))
            return max(0.0, min(100.0, 100.0 - idle))
    return 0.0


def _parse_memory(lines: list[str]) -> float:
    for line in lines:
        if line.startswith("Mem:"):
            parts = line.split()
            try:
                total = float(parts[1])
                used = float(parts[2])
                return (used / total) * 100.0 if total else 0.0
            except (ValueError, IndexError):
                continue
    return 0.0


def _parse_disk(lines: list[str]) -> float:
    if len(lines) >= 2:
        parts = lines[1].split()
        if len(parts) >= 5:
            try:
                return float(parts[4].rstrip("%"))
            except ValueError:
                pass
    return 0.0


def _parse_load(lines: list[str]) -> tuple[float, float, float]:
    text = " ".join(lines)
    match = re.search(r"load average[s]?:\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)", text)
    if match:
        return (
            float(match.group(1)),
            float(match.group(2)),
            float(match.group(3)),
        )
    return 0.0, 0.0, 0.0


def _parse_zombie(lines: list[str]) -> int:
    if lines:
        try:
            return int(lines[0].strip())
        except ValueError:
            pass
    return 0


def _parse_netdev(lines: list[str]) -> tuple[int, int]:
    for line in lines:
        if ":" not in line or line.strip().startswith("Inter") or line.strip().startswith("face"):
            continue
        name, stats = line.split(":", 1)
        name = name.strip()
        if name == "lo":
            continue
        parts = stats.split()
        if len(parts) >= 9:
            try:
                return int(parts[0]), int(parts[8])
            except ValueError:
                continue
    return 0, 0


def _parse_network(lines1: list[str], lines2: list[str]) -> tuple[int, int]:
    rx1, tx1 = _parse_netdev(lines1)
    rx2, tx2 = _parse_netdev(lines2)
    return max(0, rx2 - rx1), max(0, tx2 - tx1)


def parse_remote_output(node: str, output: str) -> MetricSnapshot:
    """Parse the shell output returned by remote_metric_command."""
    lines = output.splitlines()

    cpu_lines = _section(lines, "CPU")
    mem_lines = _section(lines, "MEM")
    disk_lines = _section(lines, "DISK")
    load_lines = _section(lines, "LOAD")
    zombie_lines = _section(lines, "ZOMBIE")
    net1_lines = _section(lines, "NET1")
    net2_lines = _section(lines, "NET2")

    load_1, load_5, load_15 = _parse_load(load_lines)
    network_in, network_out = _parse_network(net1_lines, net2_lines)

    return MetricSnapshot(
        node=node,
        timestamp=datetime.now(),
        cpu_percent=_parse_cpu(cpu_lines),
        memory_percent=_parse_memory(mem_lines),
        disk_percent=_parse_disk(disk_lines),
        load_1=load_1,
        load_5=load_5,
        load_15=load_15,
        zombie_count=_parse_zombie(zombie_lines),
        network_in_bytes=network_in,
        network_out_bytes=network_out,
    )
