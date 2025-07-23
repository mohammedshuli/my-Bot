import MetaTrader5 as mt5
import logging
import pytz
import datetime
from .constants import TIMEFRAME_MAP, MT5_TIMEZONE

def initialize_mt5():
    """Initializes MetaTrader 5 connection."""
    if not mt5.initialize():
        logging.error(f"Failed to initialize MT5: {mt5.last_error()}")
        return False
    logging.info("MT5 initialized successfully.")
    return True

def shutdown_mt5():
    """Shuts down MetaTrader 5 connection."""
    mt5.shutdown()
    logging.info("MT5 connection shut down.")

def get_symbol_info(symbol):
    """Retrieves symbol information, ensuring it's visible."""
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        logging.error(f"Failed to get symbol info for {symbol}. Error: {mt5.last_error()}")
        return None
    if not symbol_info.visible:
        logging.info(f"{symbol} is not visible in MarketWatch. Trying to show it.")
        if not mt5.symbol_select(symbol, True):
            logging.error(f"Failed to show {symbol} in MarketWatch. Error: {mt5.last_error()}")
            return None
    return symbol_info

def get_account_info():
    """Retrieves account information."""
    account_info = mt5.account_info()
    if account_info is None:
        logging.error(f"Failed to get account info. Error: {mt5.last_error()}")
        return None
    return account_info

def get_open_position(symbol, magic_number):
    """Returns the first open position for the given symbol and magic number, or None."""
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        logging.error(f"Failed to get positions. Error: {mt5.last_error()}")
        return None
    for pos in positions:
        if pos.magic == magic_number:
            return pos
    return None

def get_current_tick(symbol):
    """Fetches current tick data for a symbol."""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logging.error(f"Failed to get tick data for {symbol}. Error: {mt5.last_error()}")
    return tick

def get_mt5_timeframe(timeframe_str):
    """Converts a string timeframe to MT5 timeframe constant."""
    return TIMEFRAME_MAP.get(timeframe_str)

def get_mt5_current_time():
    """Returns the current time in the MT5 server's timezone (UTC by default)."""
    tz = pytz.timezone(MT5_TIMEZONE)
    return datetime.datetime.now(tz)