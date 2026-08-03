"""Thread-safe in-memory state for the web UI and Prometheus metrics."""
from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field

from inframon.models import Alert, MetricSnapshot


@dataclass
class State:
    """Singleton-ish state container shared across threads."""

    _lock: threading.Lock = field(default_factory=threading.Lock)
    _snapshots: dict[str, MetricSnapshot] = field(default_factory=dict)
    _alerts: dict[str, list[Alert]] = field(default_factory=lambda: defaultdict(list))

    def update(self, node: str, snapshot: MetricSnapshot) -> None:
        with self._lock:
            self._snapshots[node] = snapshot

    def add_alert(self, alert: Alert) -> None:
        with self._lock:
            self._alerts[alert.node].append(alert)

    def clear_alerts(self, node: str | None = None) -> None:
        with self._lock:
            if node:
                self._alerts[node] = []
            else:
                self._alerts = defaultdict(list)

    def snapshots(self) -> dict[str, MetricSnapshot]:
        with self._lock:
            return dict(self._snapshots)

    def alerts(self, node: str | None = None) -> list[Alert]:
        with self._lock:
            if node:
                return list(self._alerts.get(node, []))
            return [a for alerts in self._alerts.values() for a in alerts]


# Global state object used by monitor and web UI.
APP_STATE = State()
