####################################################################################
## Project name : Agentic AI POC                                                   #
## Business owner, Team : Data and AIA                                             #
## Notebook Author, Team: POC Team                                                 #
## Date: 2025-11-12                                                                 #
## Purpose of Notebook: Centralized logging configuration used across modules.     #
## Connections: Imported by other modules to standardize logging behavior.         #
####################################################################################

"""
Centralized logging configuration.

This module configures logging to file and console. Use `get_logger(name)` to
obtain a module-level logger. Logging is written to "logs/agent_app.log" and
to stdout with timestamps and module names.

Design goals:
 - Central place for log format and rotation (easy to extend for RotatingFileHandler).
 - Avoid print() statements across the codebase.
 - Keep logging calls lightweight and reusable by other files.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

# ###############  LOGGING SETTINGS  ###############
LOG_DIRECTORY = os.getenv("AGENT_LOG_DIR", "logs")
LOG_FILE_NAME = os.getenv("AGENT_LOG_FILE", "agent_app.log")
LOG_FILE_PATH = os.path.join(LOG_DIRECTORY, LOG_FILE_NAME)
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB per file
LOG_BACKUP_COUNT = 5
LOG_LEVEL = os.getenv("AGENT_LOG_LEVEL", "INFO").upper()
# ##################################################

os.makedirs(LOG_DIRECTORY, exist_ok=True)


def _configure_root_logger() -> None:
    """Internal: configure the root logger once."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return  # already configured

    root_logger.setLevel(LOG_LEVEL)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVEL)
    console_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Rotating file handler
    file_handler = RotatingFileHandler(
        LOG_FILE_PATH, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setLevel(LOG_LEVEL)
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Return a configured logger with the given name.

    :param name: logger name (typically __name__)
    :return: logging.Logger
    """
    _configure_root_logger()
    return logging.getLogger(name if name else __name__)
