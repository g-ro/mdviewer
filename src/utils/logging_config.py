#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Logging configuration for MDViewer."""
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional

from version import __title__

LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE = LOGS_DIR / f"{__title__.lower()}.log"

LOG_FORMAT = (
    "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - "
    "%(funcName)s() - %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(
    logger_name: str = __title__,
    log_file: Path = LOG_FILE,
    level: int = logging.INFO,
    console_level: Optional[int] = None,
) -> logging.Logger:
    logger_obj = logging.getLogger(logger_name)
    logger_obj.setLevel(level)

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    logger_obj.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level or level)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", DATE_FORMAT)
    )
    logger_obj.addHandler(console_handler)

    return logger_obj


logger = setup_logger()


def install_global_exception_hooks(root=None) -> None:
    def _excepthook(exc_type, exc_value, exc_traceback):
        if exc_type is KeyboardInterrupt:
            return
        logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = _excepthook

    if root is not None:
        try:
            def _tk_exception(exc_type, exc_value, exc_traceback):
                logger.error(
                    "Tkinter callback exception",
                    exc_info=(exc_type, exc_value, exc_traceback),
                )
            root.report_callback_exception = _tk_exception
        except Exception:
            pass


__all__ = ["logger", "setup_logger", "install_global_exception_hooks"]
