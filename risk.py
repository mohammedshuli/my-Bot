import logging
import MetaTrader5 as mt5
import datetime
import pytz
from .config import CONFIG
from .mt5_utils import get_account_info, get_mt5_current_time
from .trade_logger import trade_csv_logger
from .constants import MT5_TIMEZONE

# Using a list to hold daily_profit_loss so it can be passed by reference
# and modified within other functions.
daily_profit_loss = [0.0]
last_daily_pnl_reset_date = datetime.date.today()

def check_and_reset_daily_pnl(current_mt5_time, indicator_data_at_signal):
    """
    Checks if a new day has started based on MT5 time and resets daily P/L.
    Updates the global `daily_profit_loss` reference.
    """
    global last_daily_pnl_reset_date

    current_date = current_mt5_time.date()
    if current_date != last_daily_pnl_reset_date:
        logging.info(f"New day detected. Resetting daily profit/loss from {daily_profit_loss[0]:.2f} to 0.0.")
        trade_csv_logger.log_trade_event(
            event='Daily P/L Reset',
            symbol=CONFIG.SYMBOL,
            trade_type='', volume='', entry_price='', sl_price='', tp_price='',
            profit_loss='',
            daily_pnl=daily_profit_loss[0],
            indicator_data=indicator_data_at_signal,
            comment='New trading day'
        )
        daily_profit_loss[0] = 0.0
        last_daily_pnl_reset_date = current_date
        return True
    return False

def update_daily_pnl_from_closed_deals():
    """
    Updates the global daily_profit_loss by summing profits from closed deals
    for the current day and our bot's magic number.
    """
    timezone = pytz.timezone(MT5_TIMEZONE)
    today_start = datetime.datetime.now(timezone).replace(hour=0, minute=0, second=0, microsecond=0)
    current_time = datetime.datetime.now(timezone)
    
    deals = mt5.history_deals_get(today_start, current_time)
    
    realized_pnl_today = 0.0 
    if deals:
        realized_pnl_today = sum(deal.profit for deal in deals 
                                 if deal.magic == CONFIG.MAGIC_NUMBER and deal.entry == mt5.DEAL_ENTRY_OUT)
    
    daily_profit_loss[0] = realized_pnl_today
    logging.debug(f"Updated daily P/L from closed deals: {daily_profit_loss[0]:.2f}")


def check_daily_limits(indicator_data_at_signal):
    """
    Checks if daily loss or profit limits have been reached.
    Returns True if a limit is reached and no new trades should be opened, False otherwise.
    """
    account_info = get_account_info()
    if account_info is None:
        logging.error("Could not retrieve account info for daily limit check.")
        return True # Prevent trading if account info is unavailable

    current_balance = account_info.balance

    if CONFIG.MAX_DAILY_LOSS_PERCENT > 0 and daily_profit_loss[0] < -(current_balance * (CONFIG.MAX_DAILY_LOSS_PERCENT / 100)):
        log_message = f"Daily loss limit reached. Bot will not open new trades today. Current daily P/L: {daily_profit_loss[0]:.2f}"
        logging.warning(log_message)
        trade_csv_logger.log_trade_event(
            event='Daily Loss Limit',
            symbol=CONFIG.SYMBOL,
            trade_type='', volume='', entry_price='', sl_price='', tp_price='',
            profit_loss='',
            daily_pnl=daily_profit_loss[0],
            indicator_data=indicator_data_at_signal,
            comment=log_message
        )
        return True
    
    if CONFIG.MAX_DAILY_PROFIT_PERCENT > 0 and daily_profit_loss[0] > (current_balance * (CONFIG.MAX_DAILY_PROFIT_PERCENT / 100)):
        log_message = f"Daily profit target reached. Bot will not open new trades today. Current daily P/L: {daily_profit_loss[0]:.2f}"
        logging.info(log_message)
        trade_csv_logger.log_trade_event(
            event='Daily Profit Target',
            symbol=CONFIG.SYMBOL,
            trade_type='', volume='', entry_price='', sl_price='', tp_price='',
            profit_loss='',
            daily_pnl=daily_profit_loss[0],
            indicator_data=indicator_data_at_signal,
            comment=log_message
        )
        return True
    
    return False

def check_atr_for_trade(current_atr):
    """
    Checks if the current ATR value is sufficient for a trade.
    Returns True if ATR is acceptable, False otherwise.
    """
    if current_atr < CONFIG.MIN_ATR_FOR_TRADE:
        logging.warning(f"ATR value ({current_atr:.5f}) is too low for a trade (min: {CONFIG.MIN_ATR_FOR_TRADE:.5f}). Skipping trade.")
        return False
    return True