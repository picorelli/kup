#!/usr/bin/env python3
"""
Predictive-HPA Prediction Service

Prediction service for predictive autoscaling in Kubernetes.
Uses machine learning models to predict RPS and latency of services.

Supported models:
- Linear Regression
- Random Forest
- ARIMA (requires statsmodels)
- LSTM / Bi-LSTM (requires TensorFlow)
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import uvicorn

from service import PredictionService
from api.routes import set_prediction_service

# Logging config
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Config from environment
CONFIG = {
    "prometheus_url": os.getenv("PROMETHEUS_URL", "http://prometheus:9090"),
    "namespace": os.getenv("NAMESPACE", "predictive-hpa"),
    "update_interval": int(os.getenv("UPDATE_INTERVAL", "30")),
    "prediction_horizon": int(os.getenv("PREDICTION_HORIZON", "30")),
    "history_window": int(os.getenv("HISTORY_WINDOW", "120")),
    "default_model": os.getenv("DEFAULT_MODEL", "random_forest"),
    "metrics_port": int(os.getenv("METRICS_PORT", "9091")),
    "api_port": int(os.getenv("API_PORT", "8080")),
}


# Global prediction service
prediction_service: PredictionService = None


@asynccontextmanager
async def lifespan(app):
    """Application lifecycle manager."""
    global prediction_service
    
    # Startup
    logger.info("Starting Predictive-HPA Prediction Service...")
    
    prediction_service = PredictionService(
        prometheus_url=CONFIG["prometheus_url"],
        namespace=CONFIG["namespace"],
        update_interval=CONFIG["update_interval"],
        prediction_horizon=CONFIG["prediction_horizon"],
        history_window=CONFIG["history_window"],
        default_model=CONFIG["default_model"]
    )
    
    # Inject service into routes
    from api.routes import set_prediction_service
    set_prediction_service(prediction_service)
    
    # Start background update loop with proper exception propagation
    async def _run_service():
        try:
            await prediction_service.start(CONFIG["metrics_port"])
        except Exception as e:
            logger.error(f"Prediction service crashed: {e}", exc_info=True)

    asyncio.create_task(_run_service())

    logger.info("Service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down service...")
    if prediction_service:
        prediction_service.stop()


def create_application():
    """Create FastAPI application with lifespan."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from api.routes import router
    
    app = FastAPI(
        title="Predictive-HPA Prediction Service",
        description="Prediction service for predictive autoscaling",
        version="1.0.0",
        lifespan=lifespan
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.include_router(router, prefix="/api/v1", tags=["prediction"])
    
    @app.get("/")
    async def root():
        return {
            "service": "Predictive-HPA Prediction Service",
            "version": "1.0.0",
            "docs": "/docs",
            "metrics": f":{CONFIG['metrics_port']}/metrics"
        }
    
    @app.get("/health")
    async def health():
        if prediction_service and prediction_service.is_ready:
            return {"status": "healthy"}
        return {"status": "starting"}
    
    @app.get("/ready")
    async def ready():
        if prediction_service and prediction_service.is_ready:
            return {"status": "ready"}
        return {"status": "not ready"}, 503
    
    return app


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Predictive-HPA Prediction Service")
    logger.info("=" * 60)
    logger.info("Config:")
    for key, value in CONFIG.items():
        logger.info(f"  {key}: {value}")
    logger.info("=" * 60)
    
    app = create_application()
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=CONFIG["api_port"],
        log_level="info"
    )


if __name__ == "__main__":
    main()
