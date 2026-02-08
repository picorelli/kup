"""
LSTM and Bi-LSTM models for time series prediction.
"""

from typing import Optional, List
import numpy as np
import warnings

from models.base import BaseModel, ModelType

# Try to import TensorFlow, allow fallback
try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Bidirectional, Dropout
    from tensorflow.keras.callbacks import EarlyStopping
    
    # Disable verbose TensorFlow logging
    tf.get_logger().setLevel('ERROR')
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    warnings.warn("TensorFlow not available. LSTM models will not work.")


class LSTMModel(BaseModel):
    """LSTM (Long Short-Term Memory) model."""
    
    def __init__(
        self,
        units: int = 50,
        epochs: int = 10,
        batch_size: int = 32,
        sequence_length: int = 10,
        min_samples: int = 30
    ):
        """
        Initialize LSTM model.
        
        Args:
            units: Number of LSTM units
            epochs: Training epochs
            batch_size: Batch size
            sequence_length: Input sequence length
            min_samples: Minimum samples for training
        """
        super().__init__(ModelType.LSTM, min_samples)
        self.units = units
        self.epochs = epochs
        self.batch_size = batch_size
        self.sequence_length = sequence_length
        self._model = None
        self._data: Optional[np.ndarray] = None
        self._scaler_min: float = 0.0
        self._scaler_max: float = 1.0
    
    def _normalize(self, data: np.ndarray) -> np.ndarray:
        """Normaliza dados para intervalo [0, 1]."""
        self._scaler_min = float(np.min(data))
        self._scaler_max = float(np.max(data))
        
        if self._scaler_max == self._scaler_min:
            return np.zeros_like(data)
        
        return (data - self._scaler_min) / (self._scaler_max - self._scaler_min)
    
    def _denormalize(self, value: float) -> float:
        """Desnormaliza valor para escala original."""
        return value * (self._scaler_max - self._scaler_min) + self._scaler_min
    
    def _create_sequences(self, data: np.ndarray) -> tuple:
        """Create sequences for LSTM training."""
        X, y = [], []
        
        for i in range(len(data) - self.sequence_length):
            X.append(data[i:i + self.sequence_length])
            y.append(data[i + self.sequence_length])
        
        X = np.array(X)
        y = np.array(y)
        
        # Reshape para LSTM: (samples, timesteps, features)
        X = X.reshape((X.shape[0], X.shape[1], 1))
        
        return X, y
    
    def _build_model(self) -> None:
        """Build the LSTM model."""
        self._model = Sequential([
            LSTM(self.units, activation='relu', input_shape=(self.sequence_length, 1)),
            Dropout(0.2),
            Dense(1)
        ])
        self._model.compile(optimizer='adam', loss='mse')
    
    def train(self, data: np.ndarray, **kwargs) -> bool:
        """
        Treina o modelo LSTM.
        
        Args:
            data: Array com histórico de valores
        """
        if not TENSORFLOW_AVAILABLE:
            return False
        
        if len(data) < self.min_samples:
            return False
        
        try:
            self._data = np.array(data)
            
            # Normaliza dados
            normalized_data = self._normalize(self._data)
            
            # Cria sequências
            X, y = self._create_sequences(normalized_data)
            
            if len(X) < 2:
                return False
            
            # Constrói modelo
            self._build_model()
            
            # Treina com early stopping
            early_stop = EarlyStopping(
                monitor='loss',
                patience=3,
                restore_best_weights=True
            )
            
            self._model.fit(
                X, y,
                epochs=self.epochs,
                batch_size=min(self.batch_size, len(X)),
                callbacks=[early_stop],
                verbose=0
            )
            
            self.is_trained = True
            return True
        except Exception:
            return False
    
    def predict(self, horizon: int = 1) -> Optional[float]:
        """
        Prediz o valor para o horizonte especificado.
        
        Args:
            horizon: Número de passos à frente
        """
        if not self.is_trained or self._model is None or self._data is None:
            return None
        
        try:
            # Normaliza dados
            normalized_data = self._normalize(self._data)
            
            # Usa última sequência
            last_sequence = normalized_data[-self.sequence_length:]
            current_input = last_sequence.reshape((1, self.sequence_length, 1))
            
            # Prediz iterativamente até o horizonte
            prediction = None
            for _ in range(horizon):
                prediction = self._model.predict(current_input, verbose=0)[0, 0]
                
                # Atualiza sequência para próxima predição
                current_input = np.roll(current_input, -1, axis=1)
                current_input[0, -1, 0] = prediction
            
            # Desnormaliza
            result = self._denormalize(float(prediction))
            return max(0.0, result)
        except Exception:
            return None
    
    @staticmethod
    def is_available() -> bool:
        """Check if TensorFlow is available."""
        return TENSORFLOW_AVAILABLE


class BiLSTMModel(LSTMModel):
    """Modelo Bidirectional LSTM."""
    
    def __init__(
        self,
        units: int = 50,
        epochs: int = 10,
        batch_size: int = 32,
        sequence_length: int = 10,
        min_samples: int = 30
    ):
        super().__init__(units, epochs, batch_size, sequence_length, min_samples)
        self.model_type = ModelType.BI_LSTM
    
    def _build_model(self) -> None:
        """Build the Bi-LSTM model."""
        self._model = Sequential([
            Bidirectional(
                LSTM(self.units, activation='relu'),
                input_shape=(self.sequence_length, 1)
            ),
            Dropout(0.2),
            Dense(1)
        ])
        self._model.compile(optimizer='adam', loss='mse')
