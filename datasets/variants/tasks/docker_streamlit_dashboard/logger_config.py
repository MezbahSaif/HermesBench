#!/usr/bin/env python3
"""Structured logging configuration with RotatingFileHandler.

Configures the application logger to write structured log entries to console and
file, rotating when files exceed max_bytes with a configurable backup count.
"""

import logging
import logging.handlers
import os
from datetime import datetime


def get_logger(name="dashboard"):
    """Create and configure the main dashboard logger."""
    logger = logging.getLogger(name)

    # Guard against double-registration (e.g., when called multiple times)
    if any(isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers):
        return logger
    
    # Set level from environment or default to INFO
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler (always enabled)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler with RotatingFileHandler for structured log rotation
    log_dir = os.environ.get("LOG_DIR", "/data/logs")
    os.makedirs(log_dir, exist_ok=True)
    
    file_path = os.path.join(log_dir, "app.log")
    
    max_bytes = int(os.environ.get("LOG_MAX_BYTES", "10485760"))  # 10 MB default
    backup_count = int(os.environ.get("LOG_BACKUP_COUNT", "5"))
    
    file_handler = logging.handlers.RotatingFileHandler(
        filename=file_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


# Initialize the default logger at module load time
_logger = get_logger()
