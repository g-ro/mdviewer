#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Renderer abstraction layer.

Defines ``RendererProtocol`` and two concrete adapters:
  ``TkinterwebRenderer``   — full HTML + CSS via tkinterweb.HtmlFrame
  ``ScrolledTextRenderer`` — plain-text fallback when tkinterweb is absent

Use ``make_renderer(parent)`` to get the best available renderer.
Swapping the backend now requires zero changes in DocumentViewer.
"""
from __future__ import annotations

import tkinter as tk
from typing import Protocol, runtime_checkable


@runtime_checkable
class RendererProtocol(Protocol):
    """Minimal contract any HTML renderer must satisfy."""

    def load_html(self, html: str, base_url: str = "") -> None: ...
    def get_widget(self) -> tk.Widget: ...


class TkinterwebRenderer:
    """Renders HTML + CSS via a single tkinterweb.HtmlFrame."""

    def __init__(self, parent: tk.Widget) -> None:
        from tkinterweb import HtmlFrame
        self._frame: tk.Widget = HtmlFrame(
            parent, messages_enabled=False, vertical_scrollbar=True
        )

    def load_html(self, html: str, base_url: str = "") -> None:
        try:
            self._frame.load_html(html, base_url=base_url)
        except TypeError:
            # Older tkinterweb versions may not accept base_url
            self._frame.load_html(html)

    def get_widget(self) -> tk.Widget:
        return self._frame


class ScrolledTextRenderer:
    """Plain-text fallback: strips HTML tags and displays raw markdown text."""

    def __init__(self, parent: tk.Widget) -> None:
        import re
        from tkinter.scrolledtext import ScrolledText
        self._re     = re
        self._widget = ScrolledText(parent, wrap=tk.WORD, font=("Courier New", 11))

    def load_html(self, html: str, base_url: str = "") -> None:
        plain = self._re.sub(r"<[^>]+>", "", html)
        self._widget.config(state=tk.NORMAL)
        self._widget.delete("1.0", tk.END)
        self._widget.insert(tk.END, plain)
        self._widget.config(state=tk.DISABLED)

    def get_widget(self) -> tk.Widget:
        return self._widget


def make_renderer(parent: tk.Widget) -> RendererProtocol:
    """Return the best available renderer for *parent*."""
    try:
        return TkinterwebRenderer(parent)
    except ImportError:
        from utils.logging_config import logger
        logger.warning("tkinterweb not available — using plain-text renderer")
        return ScrolledTextRenderer(parent)
