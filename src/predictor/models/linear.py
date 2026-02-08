"""
Linear regression model for time series prediction.
"""

from typing import Optional
import numpy as np
from sklearn.linear_model import LinearRegression

from models.base import BaseModel, ModelType


class LinearModel(BaseModel):
    """Simple linear regression model."""
    
    def __init__(self, min_samples: int = 5):
        super().__init__(ModelType.LINEAR, min_samples)
        self._model: Optional[LinearRegression] = None
        self._last_index: int = 0
    
    def train(self, data: np.ndarray, **kwargs) -> bool:
        """
        Train the linear regression model.
        
        Args:
            data: Array with value history
        """
        if len(data) < self.min_samples:
            return False
        
        try:
            X = np.array(range(len(data))).reshape(-1, 1)
            y = np.array(data)
            
            self._model = LinearRegression()
            self._model.fit(X, y)
            self._last_index = len(data)
            self.is_trained = True
            
            return True
        except Exception:
            return False
    
    def predict(self, horizon: int = 1) -> Optional[float]:
        """
        Predict value for the given horizon.
        
        Args:
            horizon: Number of steps ahead
        """
        if not self.is_trained or self._model is None:
            return None
        
        try:
            prediction = self._model.predict([[self._last_index + horizon]])[0]
            return max(0.0, float(prediction))
        except Exception:
            return None


