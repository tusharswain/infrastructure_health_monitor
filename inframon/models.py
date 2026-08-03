"""Shared data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Severity(str, Enum):
    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


@dataclass
class MetricSnapshot:
    node: str
    timestamp: datetime = field(default_factory=lambda: datetime.now())
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    network_in_bytes: int = 0
    network_out_bytes: int = 0
    load_1: float = 0.0
    load_5: float = 0.0
    load_15: float = 0.0
    swap_percent: float = 0.0
    zombie_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "node": self.node,
            "timestamp": self.timestamp.isoformat(),
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "disk_percent": self.disk_percent,
            "network_in_bytes": self.network_in_bytes,
            "network_out_bytes": self.network_out_bytes,
            "load_1": self.load_1,
            "load_5": self.load_5,
            "load_15": self.load_15,
            "swap_percent": self.swap_percent,
            "zombie_count": self.zombie_count,
        }


@dataclass
class Alert:
    node: str
    metric: str
    severity: Severity
    value: float
    threshold: float
    message: str
    suggestions: list[str]
    actions: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now())
    resolved: bool = False

    def __str__(self) -> str:
        return (
            f"[{self.severity.value}] {self.node} {self.metric}="
            f"{self.value:.2f} (threshold {self.threshold:.2f}): {self.message}"
        )


@dataclass
class RemediationLog:
    node: str
    action: str
    severity: Severity
    dry_run: bool
    success: bool | None
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now())
