import csv
import os
import datetime
import logging
from .constants import TRADE_LOG_CSV_HEADER

class TradeCsvLogger:
    def __init__(self, filename='trade_events.csv'):
        self.filename = filename
        self._ensure_header()

    def _ensure_header(self):
        """Ensures the CSV file exists and has the correct header."""
        file_exists = os.path.isfile(self.filename)
        is_file_empty = not file_exists or os.stat(self.filename).st_size == 0

        if is_file_empty:
            with open(self.filename, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(TRADE_LOG_CSV_HEADER)
            logging.info(f"Created new CSV file: {self.filename} with header.")

    def log_trade_event(self, event, symbol, trade_type, volume, entry_price,
                        sl_price, tp_price, close_price='', profit_loss='', daily_pnl='',
                        indicator_data=None, comment=''):
        """
        Logs a trade event to the CSV file.
        `indicator_data` should be a dictionary containing keys from TRADE_LOG_CSV_HEADER.
        """
        if indicator_data is None:
            indicator_data = {}

        row_data = {key: '' for key in TRADE_LOG_CSV_HEADER} # Initialize all with empty string

        row_data.update({
            'Timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'Event': event,
            'Symbol': symbol,
            'Trade Type': trade_type,
            'Volume': f"{volume:.2f}" if isinstance(volume, (float, int)) else '',
            'Entry Price': f"{entry_price:.5f}" if isinstance(entry_price, (float, int)) else '',
            'SL Price': f"{sl_price:.5f}" if isinstance(sl_price, (float, int)) else '',
            'TP Price': f"{tp_price:.5f}" if isinstance(tp_price, (float, int)) else '',
            'Close Price': f"{close_price:.5f}" if isinstance(close_price, (float, int)) else '',
            'Profit/Loss': f"{profit_loss:.2f}" if isinstance(profit_loss, (float, int)) else '',
            'Daily P/L': f"{daily_pnl:.2f}" if isinstance(daily_pnl, (float, int)) else '',
            'Comment': comment
        })

        # Add indicator data, ensuring keys exist in header
        for key, value in indicator_data.items():
            if key in TRADE_LOG_CSV_HEADER:
                row_data[key] = str(value) # Convert to string for CSV

        with open(self.filename, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=TRADE_LOG_CSV_HEADER)
            writer.writerow(row_data)
        logging.debug(f"Logged event to CSV: {event} for {symbol}")

# Global instance for easy import
trade_csv_logger = TradeCsvLogger()