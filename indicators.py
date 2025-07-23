import pandas as pd
import pandas_ta as ta
import logging
from .config import CONFIG

def calculate_all_indicators(df):
    """Calculates all required technical indicators and adds them to the DataFrame."""
    if df.empty:
        logging.warning("DataFrame is empty, cannot calculate indicators.")
        return df

    try:
        # Simple Moving Averages (SMA)
        df['sma_fast'] = ta.sma(df['close'], length=CONFIG.SMA_FAST_LENGTH)
        df['sma_slow'] = ta.sma(df['close'], length=CONFIG.SMA_SLOW_LENGTH)
        df['sma_trend'] = ta.sma(df['close'], length=CONFIG.SMA_TREND_LENGTH)

        # Average True Range (ATR)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=CONFIG.ATR_PERIOD)

        # Relative Strength Index (RSI) if enabled
        if CONFIG.ENABLE_RSI_FILTER:
            df['rsi'] = ta.rsi(df['close'], length=CONFIG.RSI_PERIOD)

        # Drop rows with NaN values resulting from indicator calculations
        df.dropna(inplace=True)

        if df.empty:
            logging.warning("DataFrame became empty after dropping NaN rows. Not enough data for indicators.")
            return df
        
        # Validate that essential columns exist after calculation and dropping NaNs
        required_cols = ['sma_fast', 'sma_slow', 'sma_trend', 'atr']
        if CONFIG.ENABLE_RSI_FILTER:
            required_cols.append('rsi')

        for col in required_cols:
            if col not in df.columns or df[col].isnull().all():
                logging.error(f"Indicator calculation failed: Required column '{col}' is missing or all NaN values after calculation.")
                return pd.DataFrame() # Return empty DataFrame to signal failure

        logging.debug(f"Indicators calculated. DataFrame tail:\n{df.tail(2)}")
        return df.copy() # Return a copy to prevent SettingWithCopyWarning
    
    except Exception as e:
        logging.error(f"Error calculating indicators: {e}")
        return pd.DataFrame()