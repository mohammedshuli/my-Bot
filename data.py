import MetaTrader5 as mt5
import pandas as pd
import logging
import datetime
import pytz
from .constants import TIMEFRAME_DURATIONS_SECONDS, MT5_TIMEZONE

def get_historical_data(symbol, timeframe_mt5, timeframe_str, bars_to_fetch):
    """
    Fetches historical OHLCV data from MT5.
    Adjusts the start time to ensure enough bars are fetched even after NaNs are dropped.
    """
    try:
        timezone = pytz.timezone(MT5_TIMEZONE)
        
        # Fetch more bars than requested to account for indicator lag and ensure DATA_BARS_TO_FETCH valid bars
        buffer_bars = 100 # Additional bars to fetch
        total_bars_to_fetch = bars_to_fetch + buffer_bars
        
        # Calculate utc_from based on timeframe duration
        # Example: For M5, (300 seconds/minute) * (300 bars + 50 buffer) = 105000 seconds
        utc_from = datetime.datetime.now(timezone) - \
                   datetime.timedelta(seconds=TIMEFRAME_DURATIONS_SECONDS.get(timeframe_str, 60) * total_bars_to_fetch)
        
        rates = mt5.copy_rates_from(symbol, timeframe_mt5, utc_from, total_bars_to_fetch)
        
        if rates is None or len(rates) == 0:
            logging.error(f"Failed to get rates for {symbol} on {timeframe_str}. Error: {mt5.last_error()}")
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        df = df[['open', 'high', 'low', 'close', 'tick_volume']]
        
        logging.debug(f"Fetched {len(df)} raw bars for {symbol} on {timeframe_str}.")
        return df

    except Exception as e:
        logging.error(f"Error fetching historical data for {symbol}: {e}")
        return pd.DataFrame()