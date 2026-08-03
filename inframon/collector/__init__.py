"""Metric collectors for local, SSH, and Kubernetes pod targets."""
from inframon.collector.k8s import K8sCollector
from inframon.collector.local import LocalCollector
from inframon.collector.ssh import SSHCollector


def get_collector(node_type: str):
    if node_type == "local":
        return LocalCollector()
    if node_type == "k8s":
        return K8sCollector()
    return SSHCollector()
