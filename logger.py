import logging
import sys
import os

def setup_logging(log_file='bot_log.log'):
    """
    Sets up the logging configuration for the bot.
    Logs INFO and above to console, DEBUG and above to file.
    Ensures no duplicate handlers on re-run in environments like notebooks.
    """
    logger = logging.getLogger()

    # Remove all existing handlers to prevent duplicate logs on re-runs
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        if isinstance(handler, logging.FileHandler):
            handler.close() # Close file handlers to release file locks

    logger.setLevel(logging.DEBUG) # Overall lowest level for the logger

    # Console Handler (INFO and above)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File Handler (DEBUG and above)
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    logging.info("Logging configured successfully.")