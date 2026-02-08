"""
Base class for predictive models.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import numpy as np


class ModelType(Enum):
    """Available model types."""
    LINEAR = "linear"
    RANDOM_FOREST = "random_forest"
    ARIMA = "arima"
    LSTM = "lstm"
    BI_LSTM = "bi_lstm"


@dataclass
class PredictionResult:
    """Prediction result."""
    value: float
    confidence: float
    model_type: ModelType
    horizon: int  # steps ahead
    timestamp: float


@dataclass
class ModelMetrics:
    """Model evaluation metrics."""
    mse: float = 0.0
    mae: float = 0.0
    rmse: float = 0.0
    mape: float = 0.0
    samples: int = 0


class BaseModel(ABC):
    """Abstract base class for predictive models."""
    
    def __init__(self, model_type: ModelType, min_samples: int = 5):
        self.model_type = model_type
        self.min_samples = min_samples
        self.is_trained = False
        self.metrics = ModelMetrics()
        self._predictions_history: List[Tuple[float, float]] = []  # (predicted, actual)
    
    @abstractmethod
    def train(self, data: np.ndarray, **kwargs) -> bool:
        """
        Train the model with the given data.
        
        Args:
            data: Numpy array with value history
            **kwargs: Model-specific parameters
            
        Returns:
            True if training succeeded
        """
        pass
    
    @abstractmethod
    def predict(self, horizon: int = 1) -> Optional[float]:
        """
        Predict for the given horizon.
        
        Args:
            horizon: Number of steps ahead to predict
            
        Returns:
            Predicted value or None if prediction not possible
        """
        pass
    
    def update_metrics(self, predicted: float, actual: float):
        """Update error metrics with new predicted/actual pair."""
        self._predictions_history.append((predicted, actual))
        
        # Keep only the last 100 predictions
        if len(self._predictions_history) > 100:
            self._predictions_history.pop(0)
        
        self._calculate_metrics()
    
    def _calculate_metrics(self):
        """Recalculate all error metrics."""
        if len(self._predictions_history) < 2:
            return
        
        predictions = np.array([p[0] for p in self._predictions_history])
        actuals = np.array([p[1] for p in self._predictions_history])
        
        errors = predictions - actuals
        
        self.metrics.mse = float(np.mean(errors ** 2))
        self.metrics.mae = float(np.mean(np.abs(errors)))
        self.metrics.rmse = float(np.sqrt(self.metrics.mse))
        
        # MAPE (evita divisão por zero)
        with np.errstate(divide='ignore', invalid='ignore'):
            mape = np.abs(errors / actuals)
            mape = np.nan_to_num(mape, nan=0.0, posinf=0.0, neginf=0.0)
            self.metrics.mape = float(np.mean(mape) * 100)
        
        self.metrics.samples = len(self._predictions_history)
    
    def get_metrics(self) -> ModelMetrics:
        """Return current model metrics."""
        return self.metrics
