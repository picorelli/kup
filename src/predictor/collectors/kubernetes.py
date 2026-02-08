"""
Kubernetes information collector.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

from kubernetes import client, config
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)


@dataclass
class ServiceInfo:
    """Kubernetes service information."""
    name: str
    namespace: str
    replicas: int
    available_replicas: int
    labels: Dict[str, str]


class KubernetesCollector:
    """Kubernetes information collector."""
    
    def __init__(self, namespace: str = "default"):
        self.namespace = namespace
        self._v1: Optional[client.CoreV1Api] = None
        self._apps_v1: Optional[client.AppsV1Api] = None
        self._initialized = False
    
    def _init_client(self):
        """Initialize Kubernetes client."""
        if self._initialized:
            return
        
        try:
            config.load_incluster_config()
            logger.info("Using in-cluster config")
        except config.ConfigException:
            try:
                config.load_kube_config()
                logger.info("Using kubeconfig")
            except Exception as e:
                logger.error(f"Failed to load Kubernetes config: {e}")
                return
        
        self._v1 = client.CoreV1Api()
        self._apps_v1 = client.AppsV1Api()
        self._initialized = True
    
    def discover_services(self) -> List[str]:
        """Discover services in the namespace."""
        self._init_client()
        
        if not self._v1:
            return []
        
        try:
            services = self._v1.list_namespaced_service(namespace=self.namespace)
            
            service_names = []
            for svc in services.items:
                # Only services with selector (routing to pods)
                if svc.spec.selector:
                    service_names.append(svc.metadata.name)
            
            return service_names
        except ApiException as e:
            logger.error(f"Error listing services: {e}")
            return []
    
    def get_service_info(self, service_name: str) -> Optional[ServiceInfo]:
        """Get detailed information for a service."""
        self._init_client()
        
        if not self._apps_v1:
            return None
        
        try:
            # Try to get corresponding deployment
            deployment = self._apps_v1.read_namespaced_deployment(
                name=service_name,
                namespace=self.namespace
            )
            
            return ServiceInfo(
                name=service_name,
                namespace=self.namespace,
                replicas=deployment.spec.replicas or 0,
                available_replicas=deployment.status.available_replicas or 0,
                labels=deployment.metadata.labels or {}
            )
        except ApiException as e:
            if e.status != 404:
                logger.error(f"Error fetching deployment {service_name}: {e}")
            return None
    
    def health_check(self) -> bool:
        """Check connectivity to the cluster."""
        self._init_client()
        
        if not self._v1:
            return False
        
        try:
            self._v1.list_namespace(limit=1)
            return True
        except Exception:
            return False
