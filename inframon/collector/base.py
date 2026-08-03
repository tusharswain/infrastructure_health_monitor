"""Base collector interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from inframon.config import Node
from inframon.models import MetricSnapshot


class BaseCollector(ABC):
    """Collect metrics from a node and return a MetricSnapshot."""

    @abstractmethod
    def collect(self, node: Node) -> MetricSnapshot:
        raise NotImplementedError

    def _snapshot(self, node: Node | str, **kwargs) -> MetricSnapshot:
        node_name = node.name if isinstance(node, Node) else node
        return MetricSnapshot(
            node=node_name,
            timestamp=datetime.now(),
            **kwargs,
        )
