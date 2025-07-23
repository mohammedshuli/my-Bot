import time
import traceback
import logging
import MetaTrader5 as mt5


# Import modules from your project structure
from .logger import setup_logging
from .config import CONFIG
from .constants import SIGNAL_HOLD, SIGNAL_BUY, SIGNAL_SELL, MT5_TIMEZONE
from .mt5_utils import initialize_mt5, shutdown_mt5, get_symbol_info, get_open_position, get_current_tick, get_mt5_timeframe, get_mt5_current_time
from .data import get_historical_data
from .indicators import calculate_all_indicators
from .strategy import generate_signal
from .execution import execute_trade, close_position, update_trailing_stop
from .risk import daily_profit_loss, check_and_reset_daily_pnl, update_daily_pnl_from_closed_deals, check_daily_limits, check_atr_for_trade
from .trade_logger import trade_csv_logger
from .utils import sleep_until_next_candle

def main_loop():
    """Main loop for the trading bot."""
    if not initialize_mt5():
        return

    symbol_info = get_symbol_info(CONFIG.SYMBOL)
    if symbol_info is None:
        shutdown_mt5()
        return

    mt5_timeframe = get_mt5_timeframe(CONFIG.TIMEFRAME)
    if mt5_timeframe is None:
        logging.error(f"Invalid timeframe string: {CONFIG.TIMEFRAME}. Exiting.")
        shutdown_mt5()
        return

    logging.info(f"🚀 Bot started for {CONFIG.SYMBOL} on {CONFIG.TIMEFRAME} timeframe.")
    logging.info("Waiting for the next candle to check for a trading signal...")

    while True:
        try:
            current_mt5_time = get_mt5_current_time()

            # --- 1. Daily P/L Management & Limits ---
            # Check and reset P/L at start of new day.
            # `indicator_data_at_signal` is passed empty here as no signal is generated yet.
            check_and_reset_daily_pnl(current_mt5_time, {}) 
            
            # Always update daily P/L from closed deals at the start of each cycle
            # This ensures it's current for risk checks and logging.
            update_daily_pnl_from_closed_deals()
            
            # Check if daily loss/profit limits are reached before proceeding
            # `indicator_data_at_signal` is passed empty here as no signal is generated yet.
            if check_daily_limits({}):
                logging.info("Daily limits reached. No new trades today. Monitoring existing positions if any.")
                # If a limit is reached, we still want to manage existing positions and trail stops
                open_pos = get_open_position(CONFIG.SYMBOL, CONFIG.MAGIC_NUMBER)
                if open_pos:
                    tick_info = get_current_tick(CONFIG.SYMBOL)
                    if tick_info:
                        current_price = tick_info.bid if open_pos.type == mt5.ORDER_TYPE_SELL else tick_info.ask
                        # Update trailing stop for the existing position
                        # We need current ATR for trailing stop. Fetch minimal data for it.
                        df_minimal = get_historical_data(CONFIG.SYMBOL, mt5_timeframe, CONFIG.TIMEFRAME, 50)
                        df_processed_minimal = calculate_all_indicators(df_minimal)
                        if not df_processed_minimal.empty:
                            current_atr_for_ts = df_processed_minimal['atr'].iloc[-1]
                            update_trailing_stop(open_pos, symbol_info, current_price, current_atr_for_ts)
                
                sleep_until_next_candle(current_mt5_time, CONFIG.TIMEFRAME)
                continue # Skip to next iteration

            # --- 2. Fetch Data and Calculate Indicators ---
            df = get_historical_data(CONFIG.SYMBOL, mt5_timeframe, CONFIG.TIMEFRAME, CONFIG.DATA_BARS_TO_FETCH)
            if df.empty:
                logging.error("No valid data for signal check. Retrying in next cycle.")
                sleep_until_next_candle(current_mt5_time, CONFIG.TIMEFRAME)
                continue
            
            df_processed = calculate_all_indicators(df.copy())
            if df_processed.empty:
                logging.error("Failed to process indicators. Retrying in next cycle.")
                sleep_until_next_candle(current_mt5_time, CONFIG.TIMEFRAME)
                continue

            current_price = df_processed['close'].iloc[-1]
            current_atr = df_processed['atr'].iloc[-1]
            
            # --- 3. Manage Open Positions (if any) ---
            open_pos = get_open_position(CONFIG.SYMBOL, CONFIG.MAGIC_NUMBER)
            if open_pos:
                logging.info(f"Position {open_pos.ticket} is open by this bot. Current daily P/L: {daily_profit_loss[0]:.2f}.")
                
                # Check for trailing stop update
                tick_info = get_current_tick(CONFIG.SYMBOL)
                if tick_info:
                    current_market_price = tick_info.bid if open_pos.type == mt5.ORDER_TYPE_SELL else tick_info.ask
                    update_trailing_stop(open_pos, symbol_info, current_market_price, current_atr)

                # We could add logic here to close position on reversal signal,
                # but for this iteration, we'll keep it simple and let SL/TP manage it.
                sleep_until_next_candle(current_mt5_time, CONFIG.TIMEFRAME)
                continue # Skip signal generation and new trade execution if a position is already open

            # --- 4. Generate Signal ---
            signal, indicator_data_at_signal = generate_signal(df_processed)
            
            logging.info(f"Signal Check: {'BUY' if signal == SIGNAL_BUY else 'SELL' if signal == SIGNAL_SELL else 'HOLD'} | Current Price: {current_price:.5f} | ATR: {current_atr:.5f}")

            # --- 5. Risk Check (ATR) ---
            if not check_atr_for_trade(current_atr):
                sleep_until_next_candle(current_mt5_time, CONFIG.TIMEFRAME)
                continue

            # --- 6. Execute Trade if Signal is BUY or SELL ---
            if signal != SIGNAL_HOLD:
                execute_trade(symbol_info, signal, current_atr, indicator_data_at_signal, daily_profit_loss)
            
            # --- 7. Wait for next candle ---
            sleep_until_next_candle(current_mt5_time, CONFIG.TIMEFRAME)

        except Exception as e:
            logging.error(f"An unexpected error occurred in the main loop: {e}")
            logging.error(f"Traceback:\n{traceback.format_exc()}")
            
            # Log unhandled exception to CSV
            csv_comment = f"Unhandled Exception: {e}"
            # Capture indicator data if it was defined before the crash
            data_for_log = locals().get('indicator_data_at_signal', {})
            
            trade_csv_logger.log_trade_event(
                event='Unhandled Error',
                symbol=CONFIG.SYMBOL,
                trade_type='', volume='', entry_price='', sl_price='', tp_price='',
                profit_loss='',
                daily_pnl=daily_profit_loss[0],
                indicator_data=data_for_log,
                comment=csv_comment
            )
            time.sleep(60) # Sleep longer on error to prevent rapid failures


if __name__ == "__main__":
    setup_logging() # Configure logging first
    trade_csv_logger._ensure_header() # Ensure CSV header is present at startup

    try:
        main_loop()
    except KeyboardInterrupt:
        logging.info("Bot stopped by user (KeyboardInterrupt).")
    finally:
        shutdown_mt5()
        logging.info("Bot application finished.")