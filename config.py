import json
import logging
import os

class Config:
    _instance = None
    _config_data = {}

    def __new__(cls, config_file='config.json'):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_config(config_file)
        return cls._instance

    def _load_config(self, config_file):
        default_config = {
            "SYMBOL": "XAUUSDm",
            "TIMEFRAME": "M1",
            "RISK_PERCENT_PER_TRADE": 1.0,
            "DEFAULT_RR_RATIO": 2.0,
            "ATR_PERIOD": 14,
            "MAGIC_NUMBER": 123456,
            "SMA_FAST_LENGTH": 5,
            "SMA_SLOW_LENGTH": 20,
            "SMA_TREND_LENGTH": 50,
            "ATR_MULTIPLIER_SL": 1.5,
            "ATR_MULTIPLIER_TP": 3.0,
            "MIN_ATR_FOR_TRADE": 0.5,
            "ENABLE_RSI_FILTER": True,
            "RSI_PERIOD": 14,
            "RSI_OVERBOUGHT": 70,
            "RSI_OVERSOLD": 30,
            "MAX_DAILY_LOSS_PERCENT": 5.0,
            "MAX_DAILY_PROFIT_PERCENT": 10.0,
            "DATA_BARS_TO_FETCH": 300,
            "MIN_DEVIATION": 20,
            "ENABLE_TRAILING_STOP": False,
            "TRAILING_STOP_ATR_FACTOR": 1.0,
            "TRAILING_STOP_MIN_PROFIT_POINTS": 50
        }

        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, config_file)
            with open(config_path, 'r') as f:
                self._config_data = json.load(f)
                # Update with any missing default keys
                for key, value in default_config.items():
                    if key not in self._config_data:
                        self._config_data[key] = value
                logging.info(f"Loaded configuration from {config_path}.")
        except FileNotFoundError:
            logging.warning(f"{config_file} not found. Creating with default settings.")
            self._config_data = default_config
            with open(config_path, 'w') as f:
                json.dump(self._config_data, f, indent=4)
        except json.JSONDecodeError:
            logging.error(f"Error decoding {config_file}. Using default settings and overwriting file.")
            self._config_data = default_config
            with open(config_path, 'w') as f:
                json.dump(self._config_data, f, indent=4)
        
    def get(self, key, default=None):
        return self._config_data.get(key, default)

    def __getattr__(self, name):
        """Allow accessing config parameters directly as attributes (e.g., config.SYMBOL)"""
        if name in self._config_data:
            return self._config_data[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

# Global config instance
CONFIG = Config()