"""
Prediction API routes.
"""

from typing import Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


# Request/response models
class PredictionRequest(BaseModel):
    """Prediction request."""
    service_name: str
    metric: str = "rps"  # rps, latency
    horizon: int = 30  # seconds
    model: Optional[str] = None  # linear, random_forest, arima, lstm


class PredictionResponse(BaseModel):
    """Prediction response."""
    service_name: str
    metric: str
    prediction: float
    confidence: float
    model_used: str
    horizon: int
    timestamp: str


class ServiceMetricsResponse(BaseModel):
    """Response with service metrics."""
    service_name: str
    current_rps: float
    current_latency: float
    predicted_rps: float
    predicted_latency: float
    replicas: int
    error_rate: float
    model_metrics: Dict[str, float]


class ModelMetricsResponse(BaseModel):
    """Response with model metrics."""
    model_type: str
    mse: float
    mae: float
    rmse: float
    mape: float
    samples: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    prometheus: bool
    kubernetes: bool
    models_available: List[str]


# Global prediction service (injected at app creation)
prediction_service = None


def set_prediction_service(service):
    """Set the prediction service."""
    global prediction_service
    prediction_service = service


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health."""
    if prediction_service is None:
        return HealthResponse(
            status="degraded",
            prometheus=False,
            kubernetes=False,
            models_available=[]
        )
    
    return HealthResponse(
        status="healthy",
        prometheus=prediction_service.prometheus_healthy,
        kubernetes=prediction_service.kubernetes_healthy,
        models_available=prediction_service.available_models
    )


@router.get("/ready")
async def readiness_check():
    """Check if service is ready."""
    if prediction_service is None:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    if not prediction_service.is_ready:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    return {"status": "ready"}


@router.get("/services", response_model=List[str])
async def list_services():
    """List discovered services."""
    if prediction_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    return prediction_service.get_services()


@router.get("/services/{service_name}", response_model=ServiceMetricsResponse)
async def get_service_metrics(service_name: str):
    """Get metrics for a specific service."""
    if prediction_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    metrics = prediction_service.get_service_metrics(service_name)
    if metrics is None:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")
    
    return metrics


@router.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    """Make prediction for a service."""
    if prediction_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    result = prediction_service.predict(
        service_name=request.service_name,
        metric=request.metric,
        horizon=request.horizon,
        model=request.model
    )
    
    if result is None:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot predict for service {request.service_name}"
        )
    
    return PredictionResponse(
        service_name=request.service_name,
        metric=request.metric,
        prediction=result["value"],
        confidence=result["confidence"],
        model_used=result["model"],
        horizon=request.horizon,
        timestamp=datetime.utcnow().isoformat()
    )


@router.get("/predict/{service_name}", response_model=PredictionResponse)
async def predict_get(
    service_name: str,
    metric: str = Query("rps", description="Metric to predict: rps or latency"),
    horizon: int = Query(30, description="Prediction horizon in seconds"),
    model: Optional[str] = Query(None, description="Model to use")
):
    """Make prediction via GET."""
    request = PredictionRequest(
        service_name=service_name,
        metric=metric,
        horizon=horizon,
        model=model
    )
    return await predict(request)


@router.get("/models", response_model=List[str])
async def list_models():
    """List available models."""
    if prediction_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    return prediction_service.available_models


@router.get("/models/{service_name}/metrics", response_model=ModelMetricsResponse)
async def get_model_metrics(
    service_name: str,
    metric: str = Query("rps", description="Metric type")
):
    """Get model metrics for a service."""
    if prediction_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    model_metrics = prediction_service.get_model_metrics(service_name, metric)
    if model_metrics is None:
        raise HTTPException(status_code=404, detail="Model not found")
    
    return ModelMetricsResponse(
        model_type=model_metrics["model_type"],
        mse=model_metrics["mse"],
        mae=model_metrics["mae"],
        rmse=model_metrics["rmse"],
        mape=model_metrics["mape"],
        samples=model_metrics["samples"]
    )
