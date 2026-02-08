"""
ARIMA model for time series prediction.
"""

from typing import Optional, Tuple
import numpy as np
import warnings

from models.base import BaseModel, ModelType

# Try to import statsmodels, allow fallback
try:
    from statsmodels.tsa.arima.model import ARIMA
    ARIMA_AVAILABLE = True
except ImportError:
    ARIMA_AVAILABLE = False
    warnings.warn("statsmodels not available. ARIMA model will not work.")


class ARIMAModel(BaseModel):
    """ARIMA (AutoRegressive Integrated Moving Average) model."""
    
    def __init__(
        self,
        order: Tuple[int, int, int] = (5, 1, 0),
        min_samples: int = 15
    ):
        """
        Initialize ARIMA model.
        
        Args:
            order: Tuple (p, d, q) ARIMA parameters
                p: autoregressive order
                d: differencing order
                q: moving average order
            min_samples: Minimum samples for training
        """
        super().__init__(ModelType.ARIMA, min_samples)
        self.order = order
        self._model = None
        self._model_fit = None
        self._data: Optional[np.ndarray] = None
    
    def train(self, data: np.ndarray, **kwargs) -> bool:
        """
        Train the ARIMA model.
        
        Args:
            data: Array with value history
        """
        if not ARIMA_AVAILABLE:
            return False
        
        if len(data) < self.min_samples:
            return False
        
        try:
            self._data = np.array(data)
            
            # Suppress statsmodels warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                
                self._model = ARIMA(self._data, order=self.order)
                self._model_fit = self._model.fit()
            
            self.is_trained = True
            return True
        except Exception as e:
            # ARIMA can fail with certain time series
            return False
    
    def predict(self, horizon: int = 1) -> Optional[float]:
        """
        Predict value for the given horizon.
        
        Args:
            horizon: Number of steps ahead
        """
        if not self.is_trained or self._model_fit is None:
            return None
        
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                
                forecast = self._model_fit.forecast(steps=horizon)
                
                if isinstance(forecast, np.ndarray):
                    prediction = forecast[-1]
                else:
                    prediction = float(forecast)
                
                return max(0.0, float(prediction))
        except Exception:
            return None
    
    def get_model_summary(self) -> Optional[str]:
        """Return ARIMA model summary."""
        if not self.is_trained or self._model_fit is None:
            return None
        
        try:
            return str(self._model_fit.summary())
        except Exception:
            return None
    
    @staticmethod
    def is_available() -> bool:
        """Check if ARIMA is available."""
        return ARIMA_AVAILABLE
