"""Local metric collector using psutil (cross-platform)."""
from __future__ import annotations

import time

import psutil

from inframon.collector.base import BaseCollector
from inframon.config import Node
from inframon.models import MetricSnapshot


class LocalCollector(BaseCollector):
    """Collect metrics from the machine running the monitor."""

    def collect(self, node: Node) -> MetricSnapshot:
        t1 = time.time()
        net1 = psutil.net_io_counters()

        # Blocks for ~1 second to sample CPU and network rate
        cpu = psutil.cpu_percent(interval=1)

        t2 = time.time()
        net2 = psutil.net_io_counters()
        elapsed = max(t2 - t1, 0.001)

        memory = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent
        load = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (0.0, 0.0, 0.0)
        swap = psutil.swap_memory().percent

        network_in = int((net2.bytes_recv - net1.bytes_recv) / elapsed)
        network_out = int((net2.bytes_sent - net1.bytes_sent) / elapsed)

        zombie_count = 0
        try:
            zombie_count = sum(
                1
                for proc in psutil.process_iter(["status"])
                if proc.info.get("status") == psutil.STATUS_ZOMBIE
            )
        except Exception:
            pass

        return self._snapshot(
            node,
            cpu_percent=cpu,
            memory_percent=memory,
            disk_percent=disk,
            load_1=load[0],
            load_5=load[1],
            load_15=load[2],
            swap_percent=swap,
            zombie_count=zombie_count,
            network_in_bytes=network_in,
            network_out_bytes=network_out,
        )
