"""Jenkins REST API client for node management."""
from __future__ import annotations

import logging
from urllib.parse import quote, urljoin

import requests

from inframon.config import JenkinsConfig

logger = logging.getLogger(__name__)


class JenkinsClient:
    """Lightweight Jenkins client that can list nodes and toggle offline state."""

    def __init__(self, config: JenkinsConfig) -> None:
        self.config = config
        self.url = config.url.rstrip("/")
        self.auth = (config.user, config.token)
        self.verify_ssl = config.verify_ssl
        self._crumb: tuple[str, str] | None = None

    def _get(self, path: str) -> dict:
        resp = requests.get(
            self._abs_url(path), auth=self.auth, verify=self.verify_ssl, timeout=20
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: dict | None = None) -> None:
        headers = self._crumb_header()
        resp = requests.post(
            self._abs_url(path),
            auth=self.auth,
            data=data or {},
            headers=headers,
            verify=self.verify_ssl,
            timeout=20,
        )
        resp.raise_for_status()

    def _abs_url(self, path: str) -> str:
        return urljoin(f"{self.url}/", path.lstrip("/"))

    def _crumb_header(self) -> dict:
        if self._crumb is None:
            try:
                crumb_data = self._get("crumbIssuer/api/json")
                self._crumb = (
                    crumb_data["crumbRequestField"],
                    crumb_data["crumb"],
                )
            except Exception:
                logger.debug("No crumb issuer or failed to fetch crumb")
                self._crumb = ("", "")
        return {self._crumb[0]: self._crumb[1]} if self._crumb[0] else {}

    def get_nodes(self) -> list[dict]:
        """Return list of Jenkins nodes including online/offline status."""
        data = self._get("computer/api/json?tree=computer[displayName,offline,offlineCause[numExecutors]{}]")
        nodes = []
        for comp in data.get("computer", []):
            name = comp.get("displayName", "")
            nodes.append(
                {
                    "name": name,
                    "offline": comp.get("offline", False),
                    "url": f"{self.url}/computer/{quote(name, safe='')}/",
                }
            )
        return nodes

    def is_offline(self, name: str) -> bool:
        """Check whether a node is currently offline."""
        try:
            node = self._get(f"computer/{quote(name, safe='')}/api/json?tree=offline")
            return node.get("offline", False)
        except Exception as exc:
            logger.error("Failed to get Jenkins node status for %s: %s", name, exc)
            return False

    def mark_offline(self, name: str, reason: str = "Infrastructure health monitor") -> None:
        """Mark a Jenkins node as temporarily offline."""
        if self.is_offline(name):
            logger.info("Node %s is already offline", name)
            return
        logger.warning("Marking Jenkins node %s offline: %s", name, reason)
        self._post(
            f"computer/{quote(name, safe='')}/markOffline",
            data={"offlineMessage": reason},
        )

    def mark_online(self, name: str) -> None:
        """Cancel offline status on a Jenkins node."""
        if not self.is_offline(name):
            logger.info("Node %s is already online", name)
            return
        logger.warning("Marking Jenkins node %s online", name)
        self._post(f"computer/{quote(name, safe='')}/cancelOffline")
