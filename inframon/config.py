"""Configuration loading and validation."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


def _deep_update(base: dict, overlay: dict) -> dict:
    for key, value in overlay.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def _load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data or {}


class Node(BaseModel):
    name: str
    host: str
    type: str = "ssh"  # local, ssh, k8s
    ssh_user: Optional[str] = None
    ssh_key: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_port: int = 22
    namespace: Optional[str] = None
    pod_name: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    allow_restart: bool = False
    # If this monitored node maps to a different Jenkins node name, set it here.
    jenkins_node_name: Optional[str] = None


class Threshold(BaseModel):
    metric: str
    warning: Optional[float] = None
    critical: Optional[float] = None
    emergency: Optional[float] = None
    window_size: int = 3
    window_type: str = "consecutive"  # consecutive or average


class JenkinsConfig(BaseModel):
    url: str
    user: str
    token: Optional[str] = None
    verify_ssl: bool = True


class SMTPConfig(BaseModel):
    host: str
    port: int = 587
    user: str
    password: Optional[str] = None
    from_addr: str
    to_addrs: list[str]
    use_tls: bool = True


class StorageConfig(BaseModel):
    type: str = "csv"
    path: str = "data/metrics"
    influx_url: Optional[str] = None
    influx_token: Optional[str] = None
    influx_org: Optional[str] = None
    influx_bucket: Optional[str] = None


class RemediationConfig(BaseModel):
    enabled: bool = False
    dry_run: bool = True
    whitelist: list[str] = Field(default_factory=list)
    max_daily_restarts: int = 3


class WebConfig(BaseModel):
    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 5000


class Settings(BaseModel):
    log_level: str = "INFO"
    interval: int = 60
    jenkins: Optional[JenkinsConfig] = None
    smtp: Optional[SMTPConfig] = None
    storage: StorageConfig = StorageConfig()
    remediation: RemediationConfig = RemediationConfig()
    notifications: dict = Field(default_factory=dict)
    web: WebConfig = WebConfig()
    thresholds: list[Threshold] = Field(default_factory=list)
    nodes: list[Node] = Field(default_factory=list)

    @field_validator("nodes", mode="before")
    @classmethod
    def _load_nodes(cls, v: Any, info) -> Any:
        if isinstance(v, list):
            return v
        # v may be a path like "config/nodes.yaml" if the user uses a scalar.
        if isinstance(v, str):
            return _load_yaml(v).get("nodes", [])
        return []


def load_settings(settings_path: str = "config/settings.yaml") -> Settings:
    data = _load_yaml(settings_path)

    # Load credentials if referenced and existing.
    creds_file = data.get("credentials_file")
    if creds_file and Path(creds_file).exists():
        creds = _load_yaml(creds_file)
        data = _deep_update(data, creds)

    # Environment overrides for common secrets.
    env_overrides: dict[str, Any] = {}
    if os.getenv("JENKINS_URL"):
        env_overrides.setdefault("jenkins", {})["url"] = os.getenv("JENKINS_URL")
    if os.getenv("JENKINS_USER"):
        env_overrides.setdefault("jenkins", {})["user"] = os.getenv("JENKINS_USER")
    if os.getenv("JENKINS_TOKEN"):
        env_overrides.setdefault("jenkins", {})["token"] = os.getenv("JENKINS_TOKEN")
    if os.getenv("SMTP_PASSWORD"):
        env_overrides.setdefault("smtp", {})["password"] = os.getenv("SMTP_PASSWORD")
    if env_overrides:
        data = _deep_update(data, env_overrides)

    # If nodes is still a path string, resolve it.
    if isinstance(data.get("nodes"), str):
        data["nodes"] = _load_yaml(data["nodes"]).get("nodes", [])

    return Settings.model_validate(data)
