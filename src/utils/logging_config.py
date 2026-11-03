#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Logging configuration for MDViewer.

Lazy initialisation
-------------------
The logger is created on first use, not at import time.  This means:
  * No directory is created just by importing this module.
  * Tests don't get a stray ``logs/`` directory in their working directory.
  * A frozen exe launched from any location writes logs to %APPDATA%\\MDViewer\\logs.

Usage
-----
    from utils.logging_config import logger
    logger.info("...")

    # In main.py only:
    from utils.logging_config import install_global_exception_hooks
    install_global_exception_hooks(root)
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

_APP_NAME         = "MDViewer"
_logger_instance: logging.Logger | None = None
_initialised      = False

_FMT_FILE    = (
    "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - "
    "%(funcName)s() - %(message)s"
)
_FMT_CONSOLE = "%(asctime)s - %(levelname)s - %(message)s"
_DATE_FMT    = "%Y-%m-%d %H:%M:%S"


def _log_path() -> Path:
    """Return the log file path, creating parent directories as needed."""
    log_dir = Path(os.environ.get("APPDATA", Path.home())) / _APP_NAME / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "mdviewer.log"


def get_logger() -> logging.Logger:
    """Return the application logger, initialising it on first call."""
    global _logger_instance, _initialised
    if _initialised:
        return _logger_instance  # type: ignore[return-value]

    _initialised = True
    instance = logging.getLogger(_APP_NAME)
    instance.setLevel(logging.INFO)

    fmt_file    = logging.Formatter(_FMT_FILE,    _DATE_FMT)
    fmt_console = logging.Formatter(_FMT_CONSOLE, _DATE_FMT)

    # File handler — skip silently if the path is not writable
    try:
        fh = logging.handlers.RotatingFileHandler(
            _log_path(), maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        fh.setFormatter(fmt_file)
        instance.addHandler(fh)
    except OSError:
        pass  # No write access — console only

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt_console)
    instance.addHandler(ch)

    _logger_instance = instance
    return instance


class _LazyLogger:
    """
    Proxy that delegates every attribute lookup to the real logger.

    Allows ``from utils.logging_config import logger`` to work throughout
    the codebase without initialising the logger at import time.
    """
    __slots__ = ()

    def __getattr__(self, name: str):
        return getattr(get_logger(), name)


# Public name — all modules import this
logger = _LazyLogger()


def install_global_exception_hooks(root=None) -> None:
    """Wire sys.excepthook and optionally the Tkinter callback hook."""

    def _excepthook(exc_type, exc_value, exc_traceback):
        if exc_type is KeyboardInterrupt:
            return
        get_logger().error(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = _excepthook

    if root is not None:
        try:
            def _tk_exception(exc_type, exc_value, exc_traceback):
                get_logger().error(
                    "Tkinter callback exception",
                    exc_info=(exc_type, exc_value, exc_traceback),
                )
            root.report_callback_exception = _tk_exception
        except Exception:
            pass


__all__ = ["logger", "get_logger", "install_global_exception_hooks"]
