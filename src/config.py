#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Application configuration — single source of truth for all tunable constants.

Import ``cfg`` wherever a setting is needed:

    from config import cfg
    tabs = cfg.max_tabs
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _default_log_dir() -> Path:
    """Platform-appropriate log directory (not yet created; logger creates it lazily)."""
    return Path(os.environ.get("APPDATA", Path.home())) / "MDViewer" / "logs"


def _default_css_path() -> Path:
    """Bundled GitHub CSS file — works in both development and frozen-exe mode."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "resources" / "github.css"
    # Development: src/config.py → src/resources/github.css
    return Path(__file__).parent / "resources" / "github.css"


@dataclass
class AppConfig:
    # ── Tab management ────────────────────────────────────────────────
    max_tabs: int = 5               # 0 = no limit

    # ── Logging ───────────────────────────────────────────────────────
    log_dir:   Path = field(default_factory=_default_log_dir)
    log_level: str  = "INFO"

    # ── Rendering ─────────────────────────────────────────────────────
    theme_css_path: Path = field(default_factory=_default_css_path)

    # ── Tab-bar colours ───────────────────────────────────────────────
    tab_color_active:   str = "#ffffff"
    tab_color_inactive: str = "#d0d0d0"
    tab_color_hover:    str = "#ebebeb"
    tab_bar_background: str = "#b8b8b8"

    # ── Markdown extensions ───────────────────────────────────────────
    md_extensions: list[str] = field(default_factory=lambda: [
        "markdown.extensions.tables",
        "markdown.extensions.fenced_code",
        "markdown.extensions.toc",
        "markdown.extensions.nl2br",
        "markdown.extensions.attr_list",
        "markdown.extensions.def_list",
        "markdown.extensions.footnotes",
    ])


# Module-level singleton — import this everywhere
cfg = AppConfig()
