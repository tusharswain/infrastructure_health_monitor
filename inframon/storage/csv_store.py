"""CSV-backed historical metric storage."""
from __future__ import annotations

import csv
import threading
from pathlib import Path

from inframon.config import StorageConfig
from inframon.models import MetricSnapshot


class CSVStore:
    """Append metric snapshots to per-node CSV files."""

    COLUMNS = [
        "timestamp",
        "node",
        "cpu_percent",
        "memory_percent",
        "disk_percent",
        "network_in_bytes",
        "network_out_bytes",
        "load_1",
        "load_5",
        "load_15",
        "swap_percent",
        "zombie_count",
    ]

    def __init__(self, config: StorageConfig) -> None:
        self.base_path = Path(config.path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def save(self, snapshot: MetricSnapshot) -> None:
        node_file = self.base_path / f"{snapshot.node}.csv"
        with self._lock:
            write_header = not node_file.exists()
            with open(node_file, "a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=self.COLUMNS)
                if write_header:
                    writer.writeheader()
                writer.writerow(self._row(snapshot))

    def _row(self, snapshot: MetricSnapshot) -> dict:
        return {
            "timestamp": snapshot.timestamp.isoformat(),
            "node": snapshot.node,
            "cpu_percent": snapshot.cpu_percent,
            "memory_percent": snapshot.memory_percent,
            "disk_percent": snapshot.disk_percent,
            "network_in_bytes": snapshot.network_in_bytes,
            "network_out_bytes": snapshot.network_out_bytes,
            "load_1": snapshot.load_1,
            "load_5": snapshot.load_5,
            "load_15": snapshot.load_15,
            "swap_percent": snapshot.swap_percent,
            "zombie_count": snapshot.zombie_count,
        }

    def read_node(self, node: str) -> list[dict]:
        node_file = self.base_path / f"{node}.csv"
        if not node_file.exists():
            return []
        with open(node_file, "r", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    def read_all(self) -> dict[str, list[dict]]:
        result: dict[str, list[dict]] = {}
        for file_path in self.base_path.glob("*.csv"):
            result[file_path.stem] = self.read_node(file_path.stem)
        return result
