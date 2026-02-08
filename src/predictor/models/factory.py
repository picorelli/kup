"""
Factory for creating predictive models.
"""

from typing import Optional
import logging

from models.base import BaseModel, ModelType
from models.linear import LinearModel
from models.random_forest import RandomForestModel
from models.arima import ARIMAModel
from models.lstm import LSTMModel, BiLSTMModel


logger = logging.getLogger(__name__)


class ModelFactory:
    """Factory for creating predictive models."""
    
    _model_classes = {
        ModelType.LINEAR: LinearModel,
        ModelType.RANDOM_FOREST: RandomForestModel,
        ModelType.ARIMA: ARIMAModel,
        ModelType.LSTM: LSTMModel,
        ModelType.BI_LSTM: BiLSTMModel,
    }
    
    @classmethod
    def create(
        cls,
        model_type: ModelType,
        **kwargs
    ) -> Optional[BaseModel]:
        """
        Create a model of the specified type.
        
        Args:
            model_type: Model type to create
            **kwargs: Model-specific parameters
            
        Returns:
            Model instance or None if not available
        """
        if model_type not in cls._model_classes:
            logger.error(f"Unknown model type: {model_type}")
            return None
        
        model_class = cls._model_classes[model_type]
        
        # Check availability for models that depend on external libraries
        if model_type == ModelType.ARIMA and not ARIMAModel.is_available():
            logger.warning("ARIMA not available (statsmodels not installed)")
            return None
        
        if model_type in (ModelType.LSTM, ModelType.BI_LSTM) and not LSTMModel.is_available():
            logger.warning("LSTM not available (TensorFlow not installed)")
            return None
        
        try:
            return model_class(**kwargs)
        except Exception as e:
            logger.error(f"Error creating model {model_type}: {e}")
            return None
    
    @classmethod
    def get_available_models(cls) -> list:
        """Return list of available models."""
        available = []
        
        for model_type in ModelType:
            if model_type == ModelType.ARIMA:
                if ARIMAModel.is_available():
                    available.append(model_type.value)
            elif model_type in (ModelType.LSTM, ModelType.BI_LSTM):
                if LSTMModel.is_available():
                    available.append(model_type.value)
            else:
                available.append(model_type.value)
        
        return available
    
    @classmethod
    def create_best_available(cls, data_size: int) -> BaseModel:
        """
        Create the best available model based on data size.
        
        Args:
            data_size: Number of samples available
            
        Returns:
            Most appropriate model for the data size
        """
        # Preference order by complexity and data requirements.
        # Thresholds calibrated for a 120s history window at 5s scrape interval
        # (max ~24 samples). LSTM requires at least 20 to form 10-step sequences
        # with enough training pairs; ARIMA requires at least 12 for stationarity
        # checks.
        if data_size >= 20 and LSTMModel.is_available():
            logger.info(f"Selected LSTM (data_size={data_size})")
            return cls.create(ModelType.LSTM)
        elif data_size >= 12 and ARIMAModel.is_available():
            logger.info(f"Selected ARIMA (data_size={data_size})")
            return cls.create(ModelType.ARIMA)
        elif data_size >= 10:
            logger.info(f"Selected RandomForest (data_size={data_size})")
            return cls.create(ModelType.RANDOM_FOREST)
        else:
            logger.info(f"Selected Linear (data_size={data_size})")
            return cls.create(ModelType.LINEAR)
