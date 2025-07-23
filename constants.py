import MetaTrader5 as mt5
import datetime

# Signal Constants
SIGNAL_HOLD = 0
SIGNAL_BUY = 1
SIGNAL_SELL = -1

# Timeframe Mappings (MT5 specific)
TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1
}

# Timeframe Durations in Seconds for scheduling
TIMEFRAME_DURATIONS_SECONDS = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H4": 14400,
    "D1": 86400,
    "W1": 604800,
    "MN1": 2592000 # Approximation, actual month duration varies
}

# CSV Trade Log Header
TRADE_LOG_CSV_HEADER = [
    'Timestamp', 'Event', 'Symbol', 'Trade Type', 'Volume', 'Entry Price',
    'SL Price', 'TP Price', 'Close Price', 'Profit/Loss', 'Daily P/L',
    'SMA Fast', 'SMA Slow', 'SMA Trend', 'ATR', 'RSI',
    'SMA Buy Cond', 'SMA Sell Cond', 'Trend Buy Cond', 'Trend Sell Cond',
    'RSI Buy Cond', 'RSI Sell Cond',
    'Comment'
]

# Order Filling Types (commonly used)
# FOC - Fill Or Kill: Entire volume must be filled or order cancelled.
# IOC - Immediate Or Cancel: Fill what's possible immediately, cancel rest.
# RETURN - Return: Similar to IOC, remaining volume returned.
# BOC - Book Or Cancel: Primarily for pending orders, places in book if not immediate.
ORDER_FILLING_TYPE = mt5.ORDER_FILLING_IOC # Changed from FOC to IOC

# Order Time Types (commonly used)
# GTC - Good Till Cancelled: Valid until explicitly cancelled.
# DAY - Valid for the current trading day.
ORDER_TIME_TYPE = mt5.ORDER_TIME_GTC

# Default timezone for MT5 operations (often UTC)
MT5_TIMEZONE = 'Etc/UTC'