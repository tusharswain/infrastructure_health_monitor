"""Tests for the threshold evaluator."""
from __future__ import annotations

from inframon.config import Threshold
from inframon.engine.evaluator import ThresholdEvaluator
from inframon.models import MetricSnapshot, Severity


def test_evaluator_emergency_after_sustained_window():
    thresholds = [
        Threshold(
            metric="cpu_percent",
            warning=70,
            critical=85,
            emergency=95,
            window_size=2,
            window_type="consecutive",
        )
    ]
    evaluator = ThresholdEvaluator(thresholds)

    # First sample is above emergency but window is not full yet
    assert evaluator.evaluate(MetricSnapshot(node="n1", cpu_percent=96)) == []

    # Second sample completes the window -> emergency alert
    alerts = evaluator.evaluate(MetricSnapshot(node="n1", cpu_percent=97))
    assert len(alerts) == 1
    assert alerts[0].severity == Severity.EMERGENCY
    assert alerts[0].metric == "cpu_percent"
    assert alerts[0].value == 97.0


def test_evaluator_warning_only():
    thresholds = [
        Threshold(
            metric="memory_percent",
            warning=70,
            critical=85,
            emergency=95,
            window_size=2,
            window_type="consecutive",
        )
    ]
    evaluator = ThresholdEvaluator(thresholds)
    evaluator.evaluate(MetricSnapshot(node="n1", memory_percent=75))
    alerts = evaluator.evaluate(MetricSnapshot(node="n1", memory_percent=76))
    assert len(alerts) == 1
    assert alerts[0].severity == Severity.WARNING


def test_evaluator_suggestions_are_specific():
    thresholds = [
        Threshold(
            metric="disk_percent",
            warning=80,
            critical=90,
            emergency=95,
            window_size=2,
            window_type="consecutive",
        )
    ]
    evaluator = ThresholdEvaluator(thresholds)
    evaluator.evaluate(MetricSnapshot(node="n1", disk_percent=92))
    alerts = evaluator.evaluate(MetricSnapshot(node="n1", disk_percent=93))
    assert alerts[0].severity == Severity.CRITICAL
    assert any(
        keyword in suggestion.lower()
        for suggestion in alerts[0].suggestions
        for keyword in ("package", "artifact", "cache", "disk")
    )
