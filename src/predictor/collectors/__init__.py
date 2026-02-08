"""
Metric collectors for the prediction service.
"""

from collectors.prometheus import PrometheusCollector
from collectors.kubernetes import KubernetesCollector

__all__ = ["PrometheusCollector", "KubernetesCollector"]
