import datetime
import pytz
import time
import logging
from .constants import TIMEFRAME_DURATIONS_SECONDS, MT5_TIMEZONE

def calculate_next_candle_open(current_mt5_time, timeframe_str):
    """
    Calculates the exact datetime of the next candle's open,
    accounting for different timeframes.
    """
    timezone = pytz.timezone(MT5_TIMEZONE)
    
    timeframe_duration_in_seconds = TIMEFRAME_DURATIONS_SECONDS.get(timeframe_str)
    if timeframe_duration_in_seconds is None:
        logging.error(f"Unsupported timeframe duration for '{timeframe_str}'. Cannot calculate next candle open.")
        return None

    if timeframe_str in ["M1", "M5", "M15", "M30", "H1", "H4"]:
        seconds_since_interval_start = (current_mt5_time.minute * 60 + current_mt5_time.second) % timeframe_duration_in_seconds
        remaining_seconds_to_next_interval_start = timeframe_duration_in_seconds - seconds_since_interval_start
        
        # If we are exactly at the start of a new candle (e.g., 19:15:00 for M5)
        # and it's not the very first run, we want to wait for the *next* full candle.
        # Otherwise, we wait for the current candle to close and the next one to open.
        # The .replace(microsecond=0) ensures exact second alignment.
        if remaining_seconds_to_next_interval_start == timeframe_duration_in_seconds and current_mt5_time.microsecond == 0:
            next_candle_open = current_mt5_time.replace(microsecond=0) + datetime.timedelta(seconds=timeframe_duration_in_seconds)
        else:
            next_candle_open = current_mt5_time.replace(microsecond=0) + datetime.timedelta(seconds=remaining_seconds_to_next_interval_start)
        
    else: # For D1, W1, MN1
        if timeframe_str == "D1":
            next_candle_open = (current_mt5_time + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif timeframe_str == "W1":
            # Calculate days until next Monday (weekday() returns 0 for Monday)
            days_until_next_monday = (0 - current_mt5_time.weekday() + 7) % 7 
            if days_until_next_monday == 0 and current_mt5_time.hour == 0 and current_mt5_time.minute == 0 and current_mt5_time.second == 0 and current_mt5_time.microsecond == 0:
                # Already at the start of a weekly candle, so wait for the next week
                next_candle_open = current_mt5_time + datetime.timedelta(weeks=1)
            else:
                next_candle_open = (current_mt5_time + datetime.timedelta(days=days_until_next_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif timeframe_str == "MN1":
            # Get start of current month
            start_of_current_month = current_mt5_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if current_mt5_time >= start_of_current_month and current_mt5_time.microsecond == 0:
                # If current time is past or at start of current month
                if current_mt5_time.month == 12:
                    next_month = 1
                    next_year = current_mt5_time.year + 1
                else:
                    next_month = current_mt5_time.month + 1
                    next_year = current_mt5_time.year
                next_candle_open = datetime.datetime(next_year, next_month, 1, 0, 0, 0, tzinfo=timezone)
            else: # If current time is before the start of the current month (unlikely with "now")
                next_candle_open = start_of_current_month
        else:
            logging.error(f"Unsupported timeframe: {timeframe_str}. Cannot calculate next candle open.")
            return None
    
    return next_candle_open

def sleep_until_next_candle(current_mt5_time, timeframe_str):
    """Calculates sleep duration and pauses execution until the next candle opens."""
    next_candle_open = calculate_next_candle_open(current_mt5_time, timeframe_str)
    
    if next_candle_open is None:
        logging.warning("Could not determine next candle open time. Sleeping for 60 seconds.")
        time.sleep(60)
        return

    sleep_seconds = (next_candle_open - current_mt5_time).total_seconds()
    
    if sleep_seconds < 0: # This can happen if time passes while calculating
        logging.warning(f"Calculated negative sleep seconds ({sleep_seconds:.2f}). Adjusting to 1 second.")
        sleep_seconds = 1
    elif sleep_seconds < 0.1: # Small buffer for very fast execution
        sleep_seconds = 0.1 # Minimum sleep to avoid busy-waiting

    # Only log if sleeping for a significant duration to avoid spamming debug logs
    if sleep_seconds > 5:
        logging.info(f"Sleeping for {int(sleep_seconds)} seconds until next candle open ({next_candle_open.strftime('%Y-%m-%d %H:%M:%S %Z')})...")
    
    time.sleep(sleep_seconds)