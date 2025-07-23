import MetaTrader5 as mt5
import logging
import datetime
import time # Added for sleep in close_position
import math # Import math module

from .config import CONFIG
from .mt5_utils import get_account_info, get_current_tick
from .trade_logger import trade_csv_logger
from .constants import SIGNAL_BUY, SIGNAL_SELL, ORDER_FILLING_TYPE, ORDER_TIME_TYPE

def calculate_position_size(symbol_info, signal_type, sl_price, risk_amount):
    """
    Calculates the optimal lot size based on risk amount, stop loss distance,
    and symbol properties (tick value, point, volume limits).
    """
    tick_info = get_current_tick(symbol_info.name)
    if tick_info is None:
        return None

    entry_price = tick_info.ask if signal_type == SIGNAL_BUY else tick_info.bid
    if entry_price is None or entry_price == 0:
        logging.error(f"Failed to get current entry price for {symbol_info.name}.")
        return None

    if sl_price == entry_price:
        logging.warning("Stop loss price is identical to entry price. Cannot calculate position size.")
        return None
    
    # Calculate price difference in points
    price_diff_points = abs(entry_price - sl_price) / symbol_info.point

    # Check broker's minimum stop level
    min_sl_distance_points = symbol_info.trade_stops_level
    if price_diff_points < min_sl_distance_points:
        logging.warning(f"Calculated stop loss distance ({price_diff_points:.0f} points) is less than broker's minimum ({min_sl_distance_points} points). Aborting trade.")
        return None

    # Calculate risk per one standard lot (1.0 lot)
    # The value of one tick (or point) can vary by symbol/broker.
    # trade_tick_value: monetary value of a tick for a volume of trade_tick_size.
    # trade_tick_size: the volume for which trade_tick_value is specified (often 1.0 or 0.01 lot).
    
    if symbol_info.trade_tick_size == 0:
        logging.error(f"symbol_info.trade_tick_size is zero for {symbol_info.name}. Cannot calculate position size.")
        return None

    # Risk in currency units for a 1.0 lot trade given the SL distance
    risk_per_standard_lot = price_diff_points * (symbol_info.trade_tick_value / symbol_info.trade_tick_size)
    
    logging.debug(f"  Entry Price: {entry_price:.{symbol_info.digits}f}, SL Price: {sl_price:.{symbol_info.digits}f}")
    logging.debug(f"  Price Diff Points: {price_diff_points:.0f}")
    logging.debug(f"  Risk per 1.0 lot (calculated): {risk_per_standard_lot:.5f}")
    logging.debug(f"  Min SL Distance Points: {min_sl_distance_points:.0f}")

    if risk_per_standard_lot <= 0:
        logging.error("Calculated risk per one lot is zero or negative. Cannot determine position size.")
        return None

    # Calculate raw lot size
    lot_size_raw = risk_amount / risk_per_standard_lot
    
    # Adjust to broker's min, max, and step volume
    lot = max(symbol_info.volume_min, min(symbol_info.volume_max, lot_size_raw))
    
    # Calculate volume_precision dynamically from volume_step
    # If volume_step is 1.0 -> 0 decimals
    # If volume_step is 0.1 -> 1 decimal
    # If volume_step is 0.01 -> 2 decimals
    # Handle potential edge cases where volume_step might be 0, or log10 of a non-positive number
    volume_precision = 0
    if symbol_info.volume_step > 0:
        volume_precision = max(0, -int(math.floor(math.log10(symbol_info.volume_step))))
    else:
        logging.warning(f"Symbol {symbol_info.name} has a non-positive volume_step ({symbol_info.volume_step}). Using 0 decimal places for volume.")

    lot = round(lot / symbol_info.volume_step) * symbol_info.volume_step
    
    # Round to the symbol's derived volume precision to avoid floating point issues
    lot = round(lot, volume_precision) # Changed from symbol_info.volume_digits
    
    logging.info(f"  Calculated raw lot size: {lot_size_raw:.{volume_precision}f}")
    logging.info(f"  Adjusted lot size: {lot:.{volume_precision}f} (Min: {symbol_info.volume_min}, Max: {symbol_info.volume_max}, Step: {symbol_info.volume_step})")

    if lot < symbol_info.volume_min:
        logging.warning(f"Calculated lot size {lot:.{volume_precision}f} is below minimum {symbol_info.volume_min:.{volume_precision}f}. Skipping trade.")
        return None
            
    return lot

def calculate_dynamic_tp_sl(symbol_info, current_atr, signal_type, entry_price):
    """
    Calculates dynamic Take Profit and Stop Loss based on ATR and R:R ratio.
    Ensures SL/TP adhere to broker's minimum stop levels.
    """
    point = symbol_info.point
    
    # Calculate initial SL and TP distances based on ATR multipliers
    sl_distance_price = current_atr * CONFIG.ATR_MULTIPLIER_SL
    tp_distance_price_atr = current_atr * CONFIG.ATR_MULTIPLIER_TP
    
    # Calculate TP distance based on Risk-Reward Ratio
    tp_distance_price_rr = sl_distance_price * CONFIG.DEFAULT_RR_RATIO
    
    # Use the larger of the two TP distances (ATR-based vs R:R based)
    tp_distance_price = max(tp_distance_price_atr, tp_distance_price_rr)

    # Convert distances to points for broker minimum checks
    sl_distance_points = sl_distance_price / point
    tp_distance_points = tp_distance_price / point
    
    min_sl_tp_distance_points = symbol_info.trade_stops_level

    # Check if calculated SL/TP distances meet broker minimums
    if sl_distance_points < min_sl_tp_distance_points:
        logging.warning(f"Calculated SL distance ({sl_distance_points:.0f} points) is less than broker's minimum ({min_sl_tp_distance_points} points). Adjusting SL.")
        sl_distance_price = min_sl_tp_distance_points * point

    if tp_distance_points < min_sl_tp_distance_points:
        logging.warning(f"Calculated TP distance ({tp_distance_points:.0f} points) is less than broker's minimum ({min_sl_tp_distance_points} points). Adjusting TP.")
        tp_distance_price = min_sl_tp_distance_points * point

    # Calculate actual SL and TP prices
    sl_price = 0.0
    tp_price = 0.0

    if signal_type == SIGNAL_BUY:
        sl_price = entry_price - sl_distance_price
        tp_price = entry_price + tp_distance_price
    elif signal_type == SIGNAL_SELL:
        sl_price = entry_price + sl_distance_price
        tp_price = entry_price - tp_distance_price

    # Round to symbol's digits
    sl_price = round(sl_price, symbol_info.digits)
    tp_price = round(tp_price, symbol_info.digits)

    # Validate calculated prices
    if sl_price <= 0 or tp_price <= 0:
        logging.error(f"Calculated SL ({sl_price}) or TP ({tp_price}) price is zero or negative. Aborting trade.")
        return None, None

    # Final check: ensure SL is not above entry for BUY or below entry for SELL, and vice versa for TP.
    if signal_type == SIGNAL_BUY and (sl_price >= entry_price or tp_price <= entry_price):
        logging.error(f"Invalid BUY SL/TP prices: SL={sl_price}, TP={tp_price}, Entry={entry_price}")
        return None, None
    if signal_type == SIGNAL_SELL and (sl_price <= entry_price or tp_price >= entry_price):
        logging.error(f"Invalid SELL SL/TP prices: SL={sl_price}, TP={tp_price}, Entry={entry_price}")
        return None, None
        
    return sl_price, tp_price

def execute_trade(symbol_info, signal, current_atr, indicator_data_at_signal, daily_profit_loss_ref):
    """
    Executes a trade based on the signal, applies risk management,
    and logs the trade event.
    daily_profit_loss_ref is a list/mutable object to reflect changes in main loop.
    """
    account_info = get_account_info()
    if account_info is None:
        return

    # Daily limits check is performed in `risk.py` before calling this.
    # ATR minimum check is also performed in `risk.py`.

    tick_info = get_current_tick(symbol_info.name)
    if tick_info is None:
        return

    entry_price = tick_info.ask if signal == SIGNAL_BUY else tick_info.bid
    if entry_price is None or entry_price == 0:
        logging.error(f"Failed to get current entry price for {symbol_info.name} before sending order.")
        return

    sl_price, tp_price = calculate_dynamic_tp_sl(symbol_info, current_atr, signal, entry_price)
    if sl_price is None or tp_price is None:
        logging.error("Failed to calculate valid Stop Loss or Take Profit prices. Trade aborted.")
        return

    risk_amount = account_info.balance * (CONFIG.RISK_PERCENT_PER_TRADE / 100)
    if risk_amount <= 0:
        logging.error("Calculated risk amount is zero or negative. Cannot open trade.")
        return

    lot = calculate_position_size(symbol_info, signal, sl_price, risk_amount)

    if lot is None or lot <= 0:
        logging.error("Calculated lot size is None or invalid. Trade aborted.")
        return

    trade_type = mt5.ORDER_TYPE_BUY if signal == SIGNAL_BUY else mt5.ORDER_TYPE_SELL
    trade_type_str = "BUY" if signal == SIGNAL_BUY else "SELL"
    request_comment = f"{trade_type_str} Signal Bot"

    # Round entry price to symbol's digits for the request
    entry_price = round(entry_price, symbol_info.digits)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol_info.name,
        "volume": lot,
        "type": trade_type,
        "price": entry_price,
        "sl": sl_price,
        "tp": tp_price,
        "deviation": CONFIG.MIN_DEVIATION,
        "magic": CONFIG.MAGIC_NUMBER,
        "comment": request_comment,
        "type_time": ORDER_TIME_TYPE,
        "type_filling": ORDER_FILLING_TYPE,
    }

    logging.info(f"Attempting to send order: {request}")
    result = mt5.order_send(request)

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"Order failed for {symbol_info.name}: retcode={result.retcode}, comment='{result.comment}'")
        logging.debug(f"Order request: {request}")
        if result.request:
            logging.debug(f"Request details: {result.request}")
        
        trade_csv_logger.log_trade_event(
            event='Trade Failed',
            symbol=symbol_info.name,
            trade_type=trade_type_str,
            volume=lot,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            profit_loss='', # N/A for failed trade
            daily_pnl=daily_profit_loss_ref[0],
            indicator_data=indicator_data_at_signal,
            comment=f"Retcode: {result.retcode}, {result.comment}"
        )
    else:
        logging.info(f"Order placed successfully for {symbol_info.name}. Deal: {result.deal}, Position: {result.order}")
        # Need to determine `volume_precision` for logging formatting here too
        volume_precision = 0
        if symbol_info.volume_step > 0:
            volume_precision = max(0, -int(math.floor(math.log10(symbol_info.volume_step))))
        logging.info(f"  Type: {trade_type_str}, Volume: {lot:.{volume_precision}f}, Price: {entry_price:.{symbol_info.digits}f}")
        logging.info(f"  SL: {sl_price:.{symbol_info.digits}f}, TP: {tp_price:.{symbol_info.digits}f}")

        trade_csv_logger.log_trade_event(
            event='Trade Opened',
            symbol=symbol_info.name,
            trade_type=trade_type_str,
            volume=lot,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            profit_loss='', # N/A for open trade
            daily_pnl=daily_profit_loss_ref[0],
            indicator_data=indicator_data_at_signal,
            comment=f"Deal: {result.deal}, Position: {result.order}"
        )

def close_position(position, symbol_info, daily_profit_loss_ref):
    """
    Closes an open position and logs the closing event.
    daily_profit_loss_ref is a list/mutable object to reflect changes in main loop.
    """
    tick_info = get_current_tick(position.symbol)
    if tick_info is None:
        logging.error(f"Failed to get tick info for {position.symbol} for closing position. Error: {mt5.last_error()}")
        return

    close_price_request = tick_info.bid if position.type == mt5.ORDER_TYPE_BUY else tick_info.ask
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": position.symbol,
        "volume": position.volume,
        "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
        "position": position.ticket,
        "price": close_price_request,
        "deviation": CONFIG.MIN_DEVIATION,
        "magic": CONFIG.MAGIC_NUMBER,
        "comment": "Close by Bot",
        "type_time": ORDER_TIME_TYPE,
        "type_filling": ORDER_FILLING_TYPE,
    }

    logging.info(f"Attempting to close position {position.ticket}: {request}")
    result = mt5.order_send(request)

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"Position close failed for {position.ticket}: retcode={result.retcode}, comment='{result.comment}'")
        trade_csv_logger.log_trade_event(
            event='Close Failed',
            symbol=position.symbol,
            trade_type='BUY' if position.type == mt5.ORDER_TYPE_BUY else 'SELL',
            volume=position.volume,
            entry_price=position.price_open,
            sl_price=position.sl,
            tp_price=position.tp,
            profit_loss='',
            daily_pnl=daily_profit_loss_ref[0],
            comment=f"Close Retcode: {result.retcode}, {result.comment}"
        )
    else:
        logging.info(f"Position {position.ticket} closed successfully. Deal: {result.deal}")
        
        realized_profit_loss = 0.0
        close_price_actual = 0.0
        
        # Give MT5 a moment to process the deal history, especially on fast closing
        time.sleep(0.5) 
        # For closing a specific position, mt5.history_deals_get(position=position.ticket) is best.
        # But if you need the specific closing deal's profit, it's better to look at the 'result' object directly.
        # The result of order_send for a closing deal usually contains 'profit' and 'price' if it's a direct deal.
        # Let's refine this to directly get info from the result object for the closing deal.
        
        # Check if result contains deal details directly.
        if hasattr(result, 'deal') and result.deal > 0:
            deal_info = mt5.history_deal_get(result.deal)
            if deal_info:
                realized_profit_loss = deal_info.profit
                close_price_actual = deal_info.price
                logging.info(f"  Realized P/L from deal {result.deal}: {realized_profit_loss:.2f}.")
            else:
                logging.warning(f"Could not retrieve deal info for deal {result.deal} after close.")
        else:
            logging.warning(f"Order send result did not contain a valid 'deal' ticket for position {position.ticket}.")

        trade_csv_logger.log_trade_event(
            event='Trade Closed',
            symbol=position.symbol,
            trade_type='BUY' if position.type == mt5.ORDER_TYPE_BUY else 'SELL',
            volume=position.volume,
            entry_price=position.price_open,
            sl_price=position.sl,
            tp_price=position.tp,
            close_price=close_price_actual,
            profit_loss=realized_profit_loss,
            daily_pnl=daily_profit_loss_ref[0], # Updated in main loop
            comment=f"Deal: {result.deal}"
        )

def update_trailing_stop(position, symbol_info, current_tick_price, current_atr):
    """
    Updates the trailing stop loss for an open position.
    """
    if not CONFIG.ENABLE_TRAILING_STOP:
        return False

    # Need to determine `volume_precision` for logging formatting here too
    volume_precision = 0
    if symbol_info.volume_step > 0:
        volume_precision = max(0, -int(math.floor(math.log10(symbol_info.volume_step))))

    if position.type == mt5.ORDER_TYPE_BUY:
        # For BUY: trailing stop moves up as price goes up
        profit_points = (current_tick_price - position.price_open) / symbol_info.point
        new_sl_price = current_tick_price - (current_atr * CONFIG.TRAILING_STOP_ATR_FACTOR)
        
        if profit_points >= CONFIG.TRAILING_STOP_MIN_PROFIT_POINTS:
            new_sl_price = max(new_sl_price, position.sl) # Only move SL up
            new_sl_price = round(new_sl_price, symbol_info.digits)

            if new_sl_price > position.sl:
                logging.info(f"Updating BUY position {position.ticket} SL from {position.sl:.{symbol_info.digits}f} to {new_sl_price:.{symbol_info.digits}f}")
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "symbol": position.symbol,
                    "position": position.ticket,
                    "sl": new_sl_price,
                    "tp": position.tp,
                    "magic": CONFIG.MAGIC_NUMBER,
                    "deviation": CONFIG.MIN_DEVIATION,
                    "comment": "Trailing SL"
                }
                result = mt5.order_send(request)
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    logging.info(f"SL updated successfully for position {position.ticket}.")
                    return True
                else:
                    logging.error(f"Failed to update SL for position {position.ticket}: {result.comment}")
                    return False
    
    elif position.type == mt5.ORDER_TYPE_SELL:
        # For SELL: trailing stop moves down as price goes down
        profit_points = (position.price_open - current_tick_price) / symbol_info.point
        new_sl_price = current_tick_price + (current_atr * CONFIG.TRAILING_STOP_ATR_FACTOR)
        
        if profit_points >= CONFIG.TRAILING_STOP_MIN_PROFIT_POINTS:
            new_sl_price = min(new_sl_price, position.sl) # Only move SL down
            new_sl_price = round(new_sl_price, symbol_info.digits)

            if new_sl_price < position.sl:
                logging.info(f"Updating SELL position {position.ticket} SL from {position.sl:.{symbol_info.digits}f} to {new_sl_price:.{symbol_info.digits}f}")
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "symbol": position.symbol,
                    "position": position.ticket,
                    "sl": new_sl_price,
                    "tp": position.tp,
                    "magic": CONFIG.MAGIC_NUMBER,
                    "deviation": CONFIG.MIN_DEVIATION,
                    "comment": "Trailing SL"
                }
                result = mt5.order_send(request)
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    logging.info(f"SL updated successfully for position {position.ticket}.")
                    return True
                else:
                    logging.error(f"Failed to update SL for position {position.ticket}: {result.comment}")
                    return False
    return False