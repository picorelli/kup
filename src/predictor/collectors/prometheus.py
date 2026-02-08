"""
Prometheus metrics collector.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class MetricSample:
    """Metric sample."""
    timestamp: float
    value: float


@dataclass
class ServiceMetrics:
    """Metrics collected for a service."""
    service_name: str
    rps: List[MetricSample]
    latency: List[MetricSample]
    latency_p50: List[MetricSample]
    latency_p95: List[MetricSample]
    latency_p99: List[MetricSample]
    error_rate: List[MetricSample]
    cpu_usage: List[MetricSample]
    memory_usage: List[MetricSample]
    last_updated: datetime


class PrometheusCollector:
    """Prometheus metrics collector."""
    
    def __init__(self, prometheus_url: str = "http://prometheus:9090"):
        self.prometheus_url = prometheus_url.rstrip("/")
        self._cache: Dict[str, ServiceMetrics] = {}
    
    def _query(self, query: str) -> Optional[List[dict]]:
        """Run instant query on Prometheus."""
        try:
            url = f"{self.prometheus_url}/api/v1/query"
            response = requests.get(url, params={"query": query}, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data["status"] == "success":
                return data["data"]["result"]
            
            logger.warning(f"Query falhou: {data.get('error', 'Unknown')}")
            return None
        except Exception as e:
            logger.error(f"Erro ao consultar Prometheus: {e}")
            return None
    
    def _query_range(
        self,
        query: str,
        start: datetime,
        end: datetime,
        step: str = "5s"
    ) -> Optional[List[dict]]:
        """Executa query range no Prometheus."""
        try:
            url = f"{self.prometheus_url}/api/v1/query_range"
            params = {
                "query": query,
                "start": start.isoformat() + "Z",
                "end": end.isoformat() + "Z",
                "step": step,
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if data["status"] == "success":
                return data["data"]["result"]
            
            return None
        except Exception as e:
            logger.error(f"Erro ao consultar Prometheus range: {e}")
            return None
    
    def _parse_samples(self, result: List[dict]) -> List[MetricSample]:
        """Converte resultado do Prometheus em lista de amostras."""
        samples = []
        
        for item in result:
            values = item.get("values", [])
            for timestamp, value in values:
                try:
                    samples.append(MetricSample(
                        timestamp=float(timestamp),
                        value=float(value)
                    ))
                except (ValueError, TypeError):
                    continue
        
        return sorted(samples, key=lambda x: x.timestamp)
    
    def collect_service_metrics(
        self,
        service_name: str,
        history_window: int = 120  # seconds
    ) -> Optional[ServiceMetrics]:
        """
        Collect all metrics for a service.
        
        Args:
            service_name: Service name
            history_window: History window in seconds
        """
        end = datetime.utcnow()
        start = end - timedelta(seconds=history_window)
        
        queries = {
            "rps": f'sum(rate(service_process_seconds_count{{service="{service_name}",namespace="predictive-hpa"}}[1m]))',
            "latency": f'sum(rate(service_process_seconds_sum{{service="{service_name}",namespace="predictive-hpa"}}[1m])) / sum(rate(service_process_seconds_count{{service="{service_name}",namespace="predictive-hpa"}}[1m]))',
            "latency_p50": f'sum(rate(service_process_seconds_sum{{service="{service_name}",namespace="predictive-hpa"}}[1m])) / sum(rate(service_process_seconds_count{{service="{service_name}",namespace="predictive-hpa"}}[1m]))',
            "latency_p95": f'sum(rate(service_process_seconds_sum{{service="{service_name}",namespace="predictive-hpa"}}[1m])) / sum(rate(service_process_seconds_count{{service="{service_name}",namespace="predictive-hpa"}}[1m]))',
            "latency_p99": f'sum(rate(service_process_seconds_sum{{service="{service_name}",namespace="predictive-hpa"}}[1m])) / sum(rate(service_process_seconds_count{{service="{service_name}",namespace="predictive-hpa"}}[1m]))',
            "error_rate": f'1 - (sum(rate(service_process_seconds_count{{service="{service_name}",namespace="predictive-hpa"}}[1m])) > 0)',
            "cpu_usage": f'avg(rate(container_cpu_usage_seconds_total{{pod=~"{service_name}.*",namespace="predictive-hpa"}}[1m]))',
            "memory_usage": f'avg(container_memory_usage_bytes{{pod=~"{service_name}.*",namespace="predictive-hpa"}})',
        }
        
        metrics = {}
        for metric_name, query in queries.items():
            result = self._query_range(query, start, end)
            if result:
                metrics[metric_name] = self._parse_samples(result)
            else:
                metrics[metric_name] = []
        
        service_metrics = ServiceMetrics(
            service_name=service_name,
            rps=metrics["rps"],
            latency=metrics["latency"],
            latency_p50=metrics["latency_p50"],
            latency_p95=metrics["latency_p95"],
            latency_p99=metrics["latency_p99"],
            error_rate=metrics["error_rate"],
            cpu_usage=metrics["cpu_usage"],
            memory_usage=metrics["memory_usage"],
            last_updated=datetime.utcnow()
        )
        
        self._cache[service_name] = service_metrics
        return service_metrics
    
    def health_check(self) -> bool:
        """Verifica se o Prometheus está acessível."""
        try:
            response = requests.get(
                f"{self.prometheus_url}/-/healthy",
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False
