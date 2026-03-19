"""Logging configuration for the application."""
import logging
import sys
import os
from pathlib import Path

# Get log level from environment or default to INFO
# This avoids circular import issues with config.py
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def setup_logger(name: str = __name__) -> logging.Logger:
    """
    Set up and configure a logger with consistent formatting.
    
    Parameters
    ----------
    name : str
        Logger name (typically __name__)
    
    Returns
    -------
    logging.Logger
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Don't add handlers if they already exist
    if logger.handlers:
        return logger
    
    # Set log level
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)
    
    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


# Root logger setup
root_logger = setup_logger("support_api")

