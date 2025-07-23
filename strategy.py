import logging
import pandas as pd
from .constants import SIGNAL_BUY, SIGNAL_SELL, SIGNAL_HOLD, TRADE_LOG_CSV_HEADER
from .config import CONFIG

def generate_signal(df):
    """
    Generates a trading signal based on SMA crossovers, trend filter, and optional RSI filter.
    Returns the signal (BUY, SELL, HOLD) and a dictionary of current indicator values/conditions.
    """
    if len(df) < 2:
        logging.warning("Not enough data points (less than 2) for signal generation after indicator calculation.")
        # Return empty indicator data
        indicator_data = {key: '' for key in TRADE_LOG_CSV_HEADER if any(k in key for k in ['SMA', 'ATR', 'RSI', 'Cond'])}
        return SIGNAL_HOLD, indicator_data

    last_bar = df.iloc[-1]
    prev_bar = df.iloc[-2]

    # Initialize indicator data dictionary
    indicator_data = {
        'SMA Fast': f"{last_bar['sma_fast']:.5f}",
        'SMA Slow': f"{last_bar['sma_slow']:.5f}",
        'SMA Trend': f"{last_bar['sma_trend']:.5f}",
        'ATR': f"{last_bar['atr']:.5f}",
        'RSI': f"{last_bar['rsi']:.2f}" if 'rsi' in last_bar and CONFIG.ENABLE_RSI_FILTER else ''
    }

    logging.debug(f"--- Signal Check for {df.index[-1]} ---")
    logging.debug(f"  Last Close: {last_bar['close']:.5f}")
    logging.debug(f"  SMA Fast ({CONFIG.SMA_FAST_LENGTH}): {last_bar['sma_fast']:.5f} (Prev: {prev_bar['sma_fast']:.5f})")
    logging.debug(f"  SMA Slow ({CONFIG.SMA_SLOW_LENGTH}): {last_bar['sma_slow']:.5f} (Prev: {prev_bar['sma_slow']:.5f})")
    logging.debug(f"  SMA Trend ({CONFIG.SMA_TREND_LENGTH}): {last_bar['sma_trend']:.5f}")
    if CONFIG.ENABLE_RSI_FILTER and 'rsi' in last_bar:
        logging.debug(f"  RSI ({CONFIG.RSI_PERIOD}): {last_bar['rsi']:.2f}")
    logging.debug(f"  Current ATR ({CONFIG.ATR_PERIOD}): {last_bar['atr']:.5f}")

    # --- Crossover Condition (Golden Cross / Death Cross) ---
    sma_buy_crossover = (prev_bar['sma_fast'] < prev_bar['sma_slow']) and \
                        (last_bar['sma_fast'] > last_bar['sma_slow'])
    sma_sell_crossover = (prev_bar['sma_fast'] > prev_bar['sma_slow']) and \
                         (last_bar['sma_fast'] < last_bar['sma_slow'])
    
    indicator_data['SMA Buy Cond'] = sma_buy_crossover
    indicator_data['SMA Sell Cond'] = sma_sell_crossover
    logging.debug(f"  SMA Buy Crossover Condition: {sma_buy_crossover}")
    logging.debug(f"  SMA Sell Crossover Condition: {sma_sell_crossover}")

    # --- Trend Filter (Price vs. Long-term SMA) ---
    trend_buy_condition = last_bar['close'] > last_bar['sma_trend']
    trend_sell_condition = last_bar['close'] < last_bar['sma_trend']
    
    indicator_data['Trend Buy Cond'] = trend_buy_condition
    indicator_data['Trend Sell Cond'] = trend_sell_condition
    logging.debug(f"  Trend Buy Condition (Close > SMA Trend): {trend_buy_condition}")
    logging.debug(f"  Trend Sell Condition (Close < SMA Trend): {trend_sell_condition}")

    # --- RSI Filter (Optional) ---
    rsi_buy_condition = True
    rsi_sell_condition = True
    if CONFIG.ENABLE_RSI_FILTER:
        if 'rsi' in df.columns and pd.notna(last_bar['rsi']):
            rsi_buy_condition = last_bar['rsi'] < CONFIG.RSI_OVERBOUGHT
            rsi_sell_condition = last_bar['rsi'] > CONFIG.RSI_OVERSOLD
            logging.debug(f"  RSI Buy Condition (RSI < {CONFIG.RSI_OVERBOUGHT}): {rsi_buy_condition}")
            logging.debug(f"  RSI Sell Condition (RSI > {CONFIG.RSI_OVERSOLD}): {rsi_sell_condition}")
        else:
            logging.warning("RSI filter enabled but 'rsi' column is missing or NaN. Temporarily ignoring RSI filter.")
            # Do NOT modify CONFIG.ENABLE_RSI_FILTER here, as it's a global setting.
            # Instead, just bypass the RSI condition for this specific signal generation.
            rsi_buy_condition = True
            rsi_sell_condition = True
            indicator_data['RSI Buy Cond'] = 'N/A (RSI Data Missing)'
            indicator_data['RSI Sell Cond'] = 'N/A (RSI Data Missing)'
    else:
        logging.debug("  RSI filter disabled globally.")
        indicator_data['RSI Buy Cond'] = 'Disabled'
        indicator_data['RSI Sell Cond'] = 'Disabled'


    # --- Final Signal Logic ---
    if sma_buy_crossover and trend_buy_condition and rsi_buy_condition:
        logging.info("ALL BUY CONDITIONS MET!")
        return SIGNAL_BUY, indicator_data
    elif sma_sell_crossover and trend_sell_condition and rsi_sell_condition:
        logging.info("ALL SELL CONDITIONS MET!")
        return SIGNAL_SELL, indicator_data
    
    logging.debug("No trade conditions met. Returning HOLD.")
    return SIGNAL_HOLD, indicator_data