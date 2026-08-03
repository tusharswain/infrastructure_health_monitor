"""Context-aware alert messages and remediation suggestions."""
from __future__ import annotations

from inframon.models import Severity


_MESSAGES: dict[str, dict[Severity, str]] = {
    "cpu_percent": {
        Severity.WARNING: "CPU usage is elevated. Runaway processes may be consuming cycles.",
        Severity.CRITICAL: "CPU is critically high. Build concurrency should be reduced.",
        Severity.EMERGENCY: "CPU is at emergency levels. The node is being taken offline.",
    },
    "memory_percent": {
        Severity.WARNING: "Memory usage is climbing. Check for memory leaks or oversized jobs.",
        Severity.CRITICAL: "Memory is critically high. OOM kills are likely.",
        Severity.EMERGENCY: "Memory is at emergency levels. Restarting safe services and taking node offline.",
    },
    "disk_percent": {
        Severity.WARNING: "Disk usage is high. Old logs and temporary files should be cleaned.",
        Severity.CRITICAL: "Disk is nearly full. Builds will fail if the disk fills.",
        Severity.EMERGENCY: "Disk is critically full. Taking node offline to prevent corruption.",
    },
    "load_1": {
        Severity.WARNING: "Load average is elevated. CPU or I/O contention is building.",
        Severity.CRITICAL: "Load average is critically high. The node cannot keep up.",
        Severity.EMERGENCY: "Load average is in emergency range. Taking node offline immediately.",
    },
    "swap_percent": {
        Severity.WARNING: "Swap is being used. Memory pressure is increasing.",
        Severity.CRITICAL: "Swap usage is critically high. Severe performance degradation.",
        Severity.EMERGENCY: "System is thrashing on swap. Taking node offline.",
    },
    "zombie_count": {
        Severity.WARNING: "Zombie processes detected. Investigate parent processes.",
        Severity.CRITICAL: "Many zombie processes. Parent services may need a restart.",
        Severity.EMERGENCY: "Zombie storm detected. Restarting parent services.",
    },
}


_SUGGESTIONS: dict[str, dict[Severity, list[str]]] = {
    "cpu_percent": {
        Severity.WARNING: [
            "Identify top CPU consumers with `ps aux --sort=-%cpu | head -n 10`",
            "Reduce Jenkins executor count if the node is overloaded",
        ],
        Severity.CRITICAL: [
            "Identify and pause or kill runaway build jobs",
            "Mark the Jenkins node offline and redirect builds",
            "Restart whitelisted high-CPU services if memory leak suspected",
        ],
        Severity.EMERGENCY: [
            "Mark Jenkins node offline immediately",
            "Restart whitelisted services configured in remediation whitelist",
            "Page on-call if node does not recover in 5 minutes",
        ],
    },
    "memory_percent": {
        Severity.WARNING: [
            "Find largest processes with `ps aux --sort=-%mem | head -n 10`",
            "Check for memory leaks in long-running agents",
        ],
        Severity.CRITICAL: [
            "Mark Jenkins node offline to stop new builds",
            "Restart suspected leaking services from whitelist",
            "Consider reducing Java heap or container memory limits",
        ],
        Severity.EMERGENCY: [
            "Take node offline immediately",
            "Restart safe services from whitelist",
            "Scale down or migrate workloads if cluster capacity allows",
        ],
    },
    "disk_percent": {
        Severity.WARNING: [
            "Run `du -sh /var/log/* /tmp/*` to find large files",
            "Trigger log rotation for heavy services",
        ],
        Severity.CRITICAL: [
            "Clean package caches (`apt-get clean`, `docker system prune -f`)",
            "Archive or delete old build artifacts",
            "Expand disk or migrate Jenkins workspace",
        ],
        Severity.EMERGENCY: [
            "Take node offline to prevent filesystem corruption",
            "Clean `/tmp` and old logs automatically if configured",
            "Provision additional storage or replace the node",
        ],
    },
    "load_1": {
        Severity.WARNING: [
            "Check `iostat -x 1` for I/O wait",
            "Review Jenkins build concurrency on this node",
        ],
        Severity.CRITICAL: [
            "Reduce running builds and mark node offline",
            "Identify runaway or stuck processes",
        ],
        Severity.EMERGENCY: [
            "Take node offline immediately",
            "Kill defunct processes and restart safe services",
        ],
    },
    "swap_percent": {
        Severity.WARNING: [
            "Identify swap consumers with `vmstat` and `smem`",
            "Reduce memory usage or add RAM",
        ],
        Severity.CRITICAL: [
            "Mark node offline and restart memory-leak suspects",
            "Consider disabling swap thrashing by tuning swappiness",
        ],
        Severity.EMERGENCY: [
            "Take node offline to protect workloads",
            "Restart safe services and add memory capacity",
        ],
    },
    "zombie_count": {
        Severity.WARNING: [
            "List zombies with `ps aux | awk '$8 ~ /Z/'`",
            "Identify parent PIDs with `ps -eo ppid,comm,stat | grep Z`",
        ],
        Severity.CRITICAL: [
            "Send SIGHUP to zombie parent processes",
            "Restart the service creating zombies",
        ],
        Severity.EMERGENCY: [
            "Restart zombie parent services from whitelist",
            "Take node offline if zombie storm continues",
        ],
    },
}


def get_message(metric: str, value: float, severity: Severity) -> str:
    base = _MESSAGES.get(metric, {}).get(
        severity, f"{metric} is at {value} ({severity.value})"
    )
    return f"{base} (value: {value:.2f})"


def get_suggestions(metric: str, severity: Severity) -> list[str]:
    return _SUGGESTIONS.get(metric, {}).get(severity, ["Investigate metric manually"])
