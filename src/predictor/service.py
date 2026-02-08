"""
Main prediction service.
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field

import numpy as np
from prometheus_client import Counter, Gauge, Histogram, start_http_server

from models import ModelFactory, ModelType, BaseModel
from collectors import PrometheusCollector, KubernetesCollector

logger = logging.getLogger(__name__)


# Prometheus metrics
PREDICTIONS_TOTAL = Counter(
    'predictions_total',
    'Total predictions made',
    ['service', 'metric', 'model']
)
PREDICTED_RPS = Gauge(
    'predicted_rps',
    'Predicted RPS for next period',
    ['service']
)
PREDICTED_LATENCY = Gauge(
    'predicted_latency_seconds',
    'Predicted latency in seconds',
    ['service']
)
PREDICTION_ERROR_MSE = Gauge(
    'prediction_error_mse',
    'Model mean squared error',
    ['service', 'metric']
)
PREDICTION_ERROR_MAE = Gauge(
    'prediction_error_mae',
    'Model mean absolute error',
    ['service', 'metric']
)
PREDICTION_ERROR_RMSE = Gauge(
    'prediction_error_rmse',
    'Model root mean squared error',
    ['service', 'metric']
)
ACTIVE_SERVICES = Gauge(
    'active_services_count',
    'Number of active services'
)
MODEL_TRAINING_TIME = Histogram(
    'model_training_seconds',
    'Model training time',
    ['model']
)


@dataclass
class ServiceState:
    """State of a monitored service."""
    name: str
    rps_history: List[float] = field(default_factory=list)
    latency_history: List[float] = field(default_factory=list)
    cpu_history: List[float] = field(default_factory=list)
    memory_history: List[float] = field(default_factory=list)
    rps_model: Optional[BaseModel] = None
    latency_model: Optional[BaseModel] = None
    last_rps_prediction: float = 0.0
    last_latency_prediction: float = 0.0
    replicas: int = 1
    last_updated: datetime = field(default_factory=datetime.utcnow)


class PredictionService:
    """Prediction service for autoscaling."""
    
    def __init__(
        self,
        prometheus_url: str = "http://prometheus:9090",
        namespace: str = "default",
        update_interval: int = 30,
        prediction_horizon: int = 30,
        history_window: int = 120,
        default_model: str = "random_forest"
    ):
        self.prometheus_url = prometheus_url
        self.namespace = namespace
        self.update_interval = update_interval
        self.prediction_horizon = prediction_horizon
        self.history_window = history_window
        self.default_model_type = ModelType(default_model)
        
        # Collectors
        self.prometheus = PrometheusCollector(prometheus_url)
        self.kubernetes = KubernetesCollector(namespace)
        
        # State
        self._services: Dict[str, ServiceState] = {}
        self._running = False
        self._is_ready = False
    
    @property
    def prometheus_healthy(self) -> bool:
        """Check Prometheus health."""
        return self.prometheus.health_check()
    
    @property
    def kubernetes_healthy(self) -> bool:
        """Check Kubernetes health."""
        return self.kubernetes.health_check()
    
    @property
    def is_ready(self) -> bool:
        """Check if service is ready."""
        return self._is_ready
    
    @property
    def available_models(self) -> List[str]:
        """Return available models."""
        return ModelFactory.get_available_models()
    
    def get_services(self) -> List[str]:
        """Return list of monitored services."""
        return list(self._services.keys())
    
    def _create_model_for_data(self, data_size: int, model_type: Optional[str] = None) -> BaseModel:
        """Create model appropriate for data size."""
        if model_type:
            try:
                mt = ModelType(model_type)
                model = ModelFactory.create(mt)
                if model:
                    return model
            except ValueError:
                pass
        
        return ModelFactory.create_best_available(data_size)
    
    def _update_service_state(self, service_name: str):
        """Update state for a service."""
        # Collect metrics from Prometheus
        metrics = self.prometheus.collect_service_metrics(
            service_name,
            self.history_window
        )
        
        if not metrics:
            return
        
        # Create or update state
        if service_name not in self._services:
            self._services[service_name] = ServiceState(name=service_name)
        
        state = self._services[service_name]
        
        # Update history
        state.rps_history = [s.value for s in metrics.rps]
        state.latency_history = [s.value for s in metrics.latency]
        state.cpu_history = [s.value for s in metrics.cpu_usage]
        state.memory_history = [s.value for s in metrics.memory_usage]
        
        # Get replicas from Kubernetes
        info = self.kubernetes.get_service_info(service_name)
        if info:
            state.replicas = info.available_replicas
        
        state.last_updated = datetime.utcnow()
    
    def _train_models(self, service_name: str):
        """Train models for a service."""
        if service_name not in self._services:
            return
        
        state = self._services[service_name]
        
        # Train RPS model
        if len(state.rps_history) >= 5:
            if state.rps_model is None:
                state.rps_model = self._create_model_for_data(len(state.rps_history))
            
            data = np.array(state.rps_history)
            state.rps_model.train(
                data,
                cpu_usage=state.cpu_history,
                memory_usage=state.memory_history
            )
        
        # Train latency model
        if len(state.latency_history) >= 5:
            if state.latency_model is None:
                state.latency_model = self._create_model_for_data(len(state.latency_history))
            
            data = np.array(state.latency_history)
            state.latency_model.train(
                data,
                cpu_usage=state.cpu_history,
                memory_usage=state.memory_history
            )
    
    def _make_predictions(self, service_name: str):
        """Make predictions for a service."""
        if service_name not in self._services:
            return
        
        state = self._services[service_name]
        horizon_steps = max(1, self.prediction_horizon // 5)  # 5s per step
        
        # RPS prediction
        if state.rps_model and state.rps_model.is_trained:
            prediction = state.rps_model.predict(horizon_steps)
            if prediction is not None:
                state.last_rps_prediction = prediction
                PREDICTED_RPS.labels(service=service_name).set(prediction)
                PREDICTIONS_TOTAL.labels(
                    service=service_name,
                    metric="rps",
                    model=state.rps_model.model_type.value
                ).inc()
                
                # Update error metrics
                if len(state.rps_history) > 0:
                    state.rps_model.update_metrics(prediction, state.rps_history[-1])
                    metrics = state.rps_model.get_metrics()
                    PREDICTION_ERROR_MSE.labels(service=service_name, metric="rps").set(metrics.mse)
                    PREDICTION_ERROR_MAE.labels(service=service_name, metric="rps").set(metrics.mae)
                    PREDICTION_ERROR_RMSE.labels(service=service_name, metric="rps").set(metrics.rmse)
        
        # Latency prediction
        if state.latency_model and state.latency_model.is_trained:
            prediction = state.latency_model.predict(horizon_steps)
            if prediction is not None:
                state.last_latency_prediction = prediction
                PREDICTED_LATENCY.labels(service=service_name).set(prediction)
                PREDICTIONS_TOTAL.labels(
                    service=service_name,
                    metric="latency",
                    model=state.latency_model.model_type.value
                ).inc()
                
                # Update error metrics
                if len(state.latency_history) > 0:
                    state.latency_model.update_metrics(prediction, state.latency_history[-1])
                    metrics = state.latency_model.get_metrics()
                    PREDICTION_ERROR_MSE.labels(service=service_name, metric="latency").set(metrics.mse)
                    PREDICTION_ERROR_MAE.labels(service=service_name, metric="latency").set(metrics.mae)
                    PREDICTION_ERROR_RMSE.labels(service=service_name, metric="latency").set(metrics.rmse)
    
    def predict(
        self,
        service_name: str,
        metric: str = "rps",
        horizon: int = 30,
        model: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Make on-demand prediction.
        
        Args:
            service_name: Service name
            metric: Metric to predict (rps or latency)
            horizon: Prediction horizon in seconds
            model: Model type to use
        """
        if service_name not in self._services:
            return None
        
        state = self._services[service_name]
        horizon_steps = max(1, horizon // 5)
        
        if metric == "rps":
            if state.rps_model is None or not state.rps_model.is_trained:
                return None
            
            prediction = state.rps_model.predict(horizon_steps)
            if prediction is None:
                return None
            
            return {
                "value": prediction,
                "confidence": 0.8,  # TODO: compute real confidence
                "model": state.rps_model.model_type.value
            }
        
        elif metric == "latency":
            if state.latency_model is None or not state.latency_model.is_trained:
                return None
            
            prediction = state.latency_model.predict(horizon_steps)
            if prediction is None:
                return None
            
            return {
                "value": prediction,
                "confidence": 0.8,
                "model": state.latency_model.model_type.value
            }
        
        return None
    
    def get_service_metrics(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Return metrics for a service."""
        if service_name not in self._services:
            return None
        
        state = self._services[service_name]
        
        current_rps = state.rps_history[-1] if state.rps_history else 0
        current_latency = state.latency_history[-1] if state.latency_history else 0
        
        model_metrics = {}
        if state.rps_model:
            m = state.rps_model.get_metrics()
            model_metrics = {
                "mse": m.mse,
                "mae": m.mae,
                "rmse": m.rmse,
                "mape": m.mape
            }
        
        return {
            "service_name": service_name,
            "current_rps": current_rps,
            "current_latency": current_latency,
            "predicted_rps": state.last_rps_prediction,
            "predicted_latency": state.last_latency_prediction,
            "replicas": state.replicas,
            "error_rate": 0.0,  # TODO: compute from history
            "model_metrics": model_metrics
        }
    
    def get_model_metrics(self, service_name: str, metric: str) -> Optional[Dict[str, Any]]:
        """Return model metrics for a service."""
        if service_name not in self._services:
            return None
        
        state = self._services[service_name]
        
        if metric == "rps" and state.rps_model:
            m = state.rps_model.get_metrics()
            return {
                "model_type": state.rps_model.model_type.value,
                "mse": m.mse,
                "mae": m.mae,
                "rmse": m.rmse,
                "mape": m.mape,
                "samples": m.samples
            }
        
        if metric == "latency" and state.latency_model:
            m = state.latency_model.get_metrics()
            return {
                "model_type": state.latency_model.model_type.value,
                "mse": m.mse,
                "mae": m.mae,
                "rmse": m.rmse,
                "mape": m.mape,
                "samples": m.samples
            }
        
        return None
    
    async def _update_loop(self):
        """Main update loop."""
        while self._running:
            try:
                # Discover services
                services = self.kubernetes.discover_services()
                ACTIVE_SERVICES.set(len(services))
                
                # Update each service
                for service_name in services:
                    self._update_service_state(service_name)
                    self._train_models(service_name)
                    self._make_predictions(service_name)
                
                self._is_ready = True
                
            except Exception as e:
                logger.error(f"Update loop error: {e}")
            
            await asyncio.sleep(self.update_interval)
    
    async def start(self, metrics_port: int = 9091):
        """Start the prediction service."""
        logger.info("Starting prediction service...")
        logger.info(f"Prometheus URL: {self.prometheus_url}")
        logger.info(f"Namespace: {self.namespace}")
        logger.info(f"Available models: {self.available_models}")

        # Start Prometheus metrics server (runs in a daemon thread, non-blocking)
        try:
            start_http_server(metrics_port)
            logger.info(f"Metrics server started on port {metrics_port}")
        except OSError as e:
            logger.error(f"Failed to start metrics server on port {metrics_port}: {e}")
            raise
        
        self._running = True
        await self._update_loop()
    
    def stop(self):
        """Stop the prediction service."""
        self._running = False
        logger.info("Prediction service stopped")
