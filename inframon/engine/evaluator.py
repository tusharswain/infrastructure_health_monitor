"""Threshold evaluator that produces context-aware alerts."""
from __future__ import annotations

from inframon.config import Threshold
from inframon.engine.suggestions import get_message, get_suggestions
from inframon.engine.window import Window
from inframon.models import Alert, MetricSnapshot, Severity


class ThresholdEvaluator:
    """Evaluate a MetricSnapshot against thresholds using a sliding window."""

    def __init__(self, thresholds: list[Threshold]) -> None:
        self.thresholds = {t.metric: t for t in thresholds}
        self.windows: dict[str, Window] = {}

    def evaluate(self, snapshot: MetricSnapshot) -> list[Alert]:
        alerts: list[Alert] = []
        for metric, threshold in self.thresholds.items():
            value = getattr(snapshot, metric, None)
            if value is None or threshold.warning is None:
                continue

            window_key = f"{snapshot.node}:{metric}"
            window = self.windows.setdefault(window_key, Window(threshold.window_size))
            window.add(float(value))

            severity, breach_value = self._determine_severity(window, threshold)
            if severity:
                alerts.append(
                    Alert(
                        node=snapshot.node,
                        metric=metric,
                        severity=severity,
                        value=float(value),
                        threshold=breach_value,
                        message=get_message(metric, float(value), severity),
                        suggestions=get_suggestions(metric, severity),
                    )
                )
        return alerts

    def _determine_severity(
        self, window: Window, threshold: Threshold
    ) -> tuple[Severity | None, float | None]:
        """Check from most to least severe and return the first breach."""
        levels = [
            (Severity.EMERGENCY, threshold.emergency),
            (Severity.CRITICAL, threshold.critical),
            (Severity.WARNING, threshold.warning),
        ]
        for severity, tval in levels:
            if tval is not None and window.is_breached(tval, threshold.window_type):
                return severity, tval
        return None, None
