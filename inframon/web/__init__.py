"""Flask web UI and Prometheus metrics endpoint."""
from inframon.web.app import create_app

__all__ = ["create_app"]
