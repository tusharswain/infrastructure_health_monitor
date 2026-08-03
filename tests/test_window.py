"""Tests for the sliding-window threshold logic."""
from __future__ import annotations

from inframon.engine.window import Window


def test_consecutive_breach():
    window = Window(3)
    assert not window.is_breached(90, "consecutive")
    window.add(95)
    assert not window.is_breached(90, "consecutive")
    window.add(96)
    assert not window.is_breached(90, "consecutive")
    window.add(97)
    assert window.is_breached(90, "consecutive")
    assert not window.is_breached(98, "consecutive")


def test_consecutive_not_sustained():
    window = Window(3)
    window.add(100)
    window.add(80)
    window.add(100)
    assert not window.is_breached(90, "consecutive")


def test_average_breach():
    window = Window(3)
    window.add(80)
    window.add(100)
    window.add(90)
    assert window.is_breached(90, "average")
    assert not window.is_breached(95, "average")
