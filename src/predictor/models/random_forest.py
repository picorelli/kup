"""
Random Forest model for time series prediction.
"""

from typing import Optional, List
import numpy as np
from sklearn.ensemble import RandomForestRegressor

from models.base import BaseModel, ModelType


class RandomForestModel(BaseModel):
    """Random Forest model with derived features."""
    
    def __init__(
        self,
        n_estimators: int = 10,
        min_samples: int = 10,
        window_size: int = 4
    ):
        super().__init__(ModelType.RANDOM_FOREST, min_samples)
        self.n_estimators = n_estimators
        self.window_size = window_size
        self._model: Optional[RandomForestRegressor] = None
        self._last_features: Optional[List[float]] = None
        self._data: Optional[np.ndarray] = None
        self._cpu_history: List[float] = []
        self._memory_history: List[float] = []
    
    def _create_features(
        self,
        data: np.ndarray,
        cpu_usage: Optional[List[float]] = None,
        memory_usage: Optional[List[float]] = None
    ) -> np.ndarray:
        """Create features for each time point."""
        features = []
        
        for i in range(len(data)):
            window_start = max(0, i - self.window_size + 1)
            window = data[window_start:i + 1]
            
            feature_vector = [
                i,  # time index
                data[i],  # current value
                np.mean(window),  # moving average
                np.std(window) if len(window) > 1 else 0,  # std dev
                np.min(window),  # min in window
                np.max(window),  # max in window
                data[i] - data[i-1] if i > 0 else 0,  # difference
            ]
            
            # Add CPU if available
            if cpu_usage and i < len(cpu_usage):
                feature_vector.append(cpu_usage[i])
            else:
                feature_vector.append(0)
            
            # Add memory if available
            if memory_usage and i < len(memory_usage):
                feature_vector.append(memory_usage[i])
            else:
                feature_vector.append(0)
            
            features.append(feature_vector)
        
        return np.array(features)
    
    def train(
        self,
        data: np.ndarray,
        cpu_usage: Optional[List[float]] = None,
        memory_usage: Optional[List[float]] = None,
        **kwargs
    ) -> bool:
        """
        Train the Random Forest model.
        
        Args:
            data: Array with value history
            cpu_usage: CPU usage history
            memory_usage: Memory usage history
        """
        if len(data) < self.min_samples:
            return False
        
        try:
            self._data = np.array(data)
            self._cpu_history = cpu_usage or []
            self._memory_history = memory_usage or []
            
            X = self._create_features(data, cpu_usage, memory_usage)
            y = np.array(data)
            
            self._model = RandomForestRegressor(
                n_estimators=self.n_estimators,
                random_state=42,
                n_jobs=-1
            )
            self._model.fit(X, y)
            
            # Store last feature for prediction
            self._last_features = X[-1].tolist()
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
        if not self.is_trained or self._model is None or self._data is None:
            return None
        
        try:
            # Create features for prediction
            last_idx = len(self._data) - 1
            window = self._data[-self.window_size:]
            
            features = [
                last_idx + horizon,
                self._data[-1],
                np.mean(window),
                np.std(window),
                np.min(window),
                np.max(window),
                self._data[-1] - self._data[-2] if len(self._data) > 1 else 0,
                self._cpu_history[-1] if self._cpu_history else 0,
                self._memory_history[-1] if self._memory_history else 0,
            ]
            
            prediction = self._model.predict([features])[0]
            return max(0.0, float(prediction))
        except Exception:
            return None
    
    def get_feature_importance(self) -> Optional[dict]:
        """Return feature importance."""
        if not self.is_trained or self._model is None:
            return None
        
        feature_names = [
            "time_index", "current_value", "moving_avg", "std_dev",
            "min_window", "max_window", "diff", "cpu_usage", "memory_usage"
        ]
        
        importances = self._model.feature_importances_
        return dict(zip(feature_names, importances.tolist()))
