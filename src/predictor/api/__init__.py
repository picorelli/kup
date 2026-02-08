"""
FastAPI for the prediction service.
"""

from api.routes import router, set_prediction_service

__all__ = ["router", "set_prediction_service"]
