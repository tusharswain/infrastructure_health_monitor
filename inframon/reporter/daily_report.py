"""Generate daily HTML/PDF trend reports."""
from __future__ import annotations

import base64
import logging
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from jinja2 import Environment, PackageLoader

from inframon.config import StorageConfig
from inframon.storage.csv_store import CSVStore

matplotlib.use("Agg")
logger = logging.getLogger(__name__)

_ENV = Environment(loader=PackageLoader("inframon", "templates"))


class DailyReport:
    """Build a daily report from historical CSV data."""

    def __init__(self, storage_config: StorageConfig, output_dir: str = "reports") -> None:
        self.store = CSVStore(storage_config)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, report_date: str, fmt: str = "html") -> Path:
        target = date.fromisoformat(report_date)
        data = self.store.read_all()

        nodes = []
        for node, rows in data.items():
            node_rows = [r for r in rows if self._parse_date(r["timestamp"]) == target]
            if not node_rows:
                continue
            summary = self._summarize(node_rows)
            chart = self._chart(node, node_rows)
            nodes.append({"name": node, "summary": summary, "chart": chart})

        nodes.sort(key=lambda n: n["name"])

        template = _ENV.get_template("daily_report.html")
        html = template.render(date=report_date, nodes=nodes)

        html_path = self.output_dir / f"report-{report_date}.html"
        html_path.write_text(html, encoding="utf-8")

        if fmt == "pdf":
            pdf_path = self.output_dir / f"report-{report_date}.pdf"
            try:
                import weasyprint

                weasyprint.HTML(string=html).write_pdf(str(pdf_path))
                return pdf_path
            except Exception as exc:
                logger.error("PDF generation failed (%s); returning HTML instead", exc)

        return html_path

    @staticmethod
    def _parse_date(ts: str) -> date:
        dt = datetime.fromisoformat(ts)
        return dt.date()

    def _summarize(self, rows: list[dict]) -> dict:
        def avg(key: str) -> float:
            values = [float(r[key]) for r in rows if r.get(key)]
            return sum(values) / len(values) if values else 0.0

        def maxv(key: str) -> float:
            values = [float(r[key]) for r in rows if r.get(key)]
            return max(values) if values else 0.0

        return {
            "avg_cpu": avg("cpu_percent"),
            "max_cpu": maxv("cpu_percent"),
            "avg_mem": avg("memory_percent"),
            "max_mem": maxv("memory_percent"),
            "avg_disk": avg("disk_percent"),
            "max_disk": maxv("disk_percent"),
            "avg_load": avg("load_1"),
            "max_load": maxv("load_1"),
            "samples": len(rows),
        }

    def _chart(self, node: str, rows: list[dict]) -> str:
        times = [datetime.fromisoformat(r["timestamp"]) for r in rows]
        cpu = [float(r["cpu_percent"]) for r in rows]
        mem = [float(r["memory_percent"]) for r in rows]
        disk = [float(r["disk_percent"]) for r in rows]
        load = [float(r["load_1"]) for r in rows]

        fig, axes = plt.subplots(2, 2, figsize=(8, 5))
        fig.suptitle(f"{node} — {len(rows)} samples", fontsize=10)

        axes[0, 0].plot(times, cpu, color="red")
        axes[0, 0].set_title("CPU %")
        axes[0, 0].set_ylim(0, 100)

        axes[0, 1].plot(times, mem, color="orange")
        axes[0, 1].set_title("Memory %")
        axes[0, 1].set_ylim(0, 100)

        axes[1, 0].plot(times, disk, color="green")
        axes[1, 0].set_title("Disk %")
        axes[1, 0].set_ylim(0, 100)

        axes[1, 1].plot(times, load, color="purple")
        axes[1, 1].set_title("Load (1m)")

        for ax in axes.flat:
            ax.tick_params(axis="x", rotation=30, labelsize=6)
            ax.grid(True, linestyle="--", alpha=0.5)

        fig.tight_layout()

        buffer = BytesIO()
        fig.savefig(buffer, format="png", dpi=120)
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode("utf-8")
        plt.close(fig)
        return image_base64
