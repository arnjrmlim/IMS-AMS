"""
logger_setup.py — Centralized logging configuration.

Logs are written to:
  - Console (stdout)
  - logs/speedface.log (rotating file, 5 MB × 5 backups)

Sensitive data (comm key, passwords, biometric templates) is NEVER logged.
"""

import logging
import logging.handlers
import os
import sys

LOG_DIR  = os.path.join(os.path.dirname(__file__), '..', 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'speedface.log')

_CONSOLE_FORMAT = '%(levelname)-8s %(message)s'
_FILE_FORMAT    = '%(asctime)s  %(levelname)-8s  %(name)s  %(message)s'
_DATE_FORMAT    = '%Y-%m-%d %H:%M:%S'


def setup_logging(debug: bool = False) -> None:
    """
    Configure root logger.
    Call once at application start-up (in run.py).

    :param debug: If True, set level to DEBUG and show tracebacks.
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    level = logging.DEBUG if debug else logging.INFO

    # Root logger
    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers if called more than once
    if root.handlers:
        return

    # --- Console handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(_CONSOLE_FORMAT))
    root.addHandler(console_handler)

    # --- Rotating file handler ---
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,   # 5 MB
        backupCount=5,
        encoding='utf-8',
    )
    file_handler.setLevel(logging.DEBUG)  # always capture full detail in file
    file_handler.setFormatter(logging.Formatter(_FILE_FORMAT, datefmt=_DATE_FORMAT))
    root.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger('zk').setLevel(logging.WARNING)
