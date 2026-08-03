"""Optional InfluxDB 2.x storage backend."""
from __future__ import annotations

import logging

from inframon.config import StorageConfig
from inframon.models import MetricSnapshot

logger = logging.getLogger(__name__)


class InfluxDBStore:
    """Write metric snapshots to InfluxDB 2.x."""

    def __init__(self, config: StorageConfig) -> None:
        self.config = config
        try:
            from influxdb_client import InfluxDBClient, Point
            from influxdb_client.client.write_api import SYNCHRONOUS

            self.client = InfluxDBClient(
                url=config.influx_url,
                token=config.influx_token,
                org=config.influx_org,
            )
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            self.Point = Point
        except Exception as exc:
            logger.error("Failed to initialise InfluxDB client: %s", exc)
            raise

    def save(self, snapshot: MetricSnapshot) -> None:
        point = (
            self.Point("node_metrics")
            .tag("node", snapshot.node)
            .field("cpu_percent", snapshot.cpu_percent)
            .field("memory_percent", snapshot.memory_percent)
            .field("disk_percent", snapshot.disk_percent)
            .field("network_in_bytes", snapshot.network_in_bytes)
            .field("network_out_bytes", snapshot.network_out_bytes)
            .field("load_1", snapshot.load_1)
            .field("load_5", snapshot.load_5)
            .field("load_15", snapshot.load_15)
            .field("swap_percent", snapshot.swap_percent)
            .field("zombie_count", snapshot.zombie_count)
            .time(snapshot.timestamp)
        )
        try:
            self.write_api.write(bucket=self.config.influx_bucket, record=point)
        except Exception as exc:
            logger.error("Failed to write InfluxDB point: %s", exc)
