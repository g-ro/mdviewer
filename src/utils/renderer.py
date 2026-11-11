#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Renderer abstraction layer.

Defines ``RendererProtocol`` and two concrete adapters:
  ``TkinterwebRenderer``   — full HTML + CSS via tkinterweb.HtmlFrame
  ``ScrolledTextRenderer`` — plain-text fallback when tkinterweb is absent

Use ``make_renderer(parent, on_navigate)`` to get the best available renderer.

Rendering strategy
------------------
Documents are loaded via ``load_url(file_uri)`` where the URI points to a
per-tab temp file managed by ``TempHtmlStore``.  This gives tkinterweb a
stable, unique URL per tab so that:

  * Switching tabs loads a different URL → no cache conflict, no ``force=True``
  * Anchor links (``#section``) resolve against the temp file's URL
    → tkinterweb can scroll to the target element naturally

Welcome and error content that requires no anchor navigation is loaded via
``load_html(html)`` directly, bypassing the file system.

Find / search
-------------
tkinterweb exposes ``find_text(text, select, ignore_case, highlight_all)``
which searches the *rendered* text (not raw HTML), highlights all matches in
one colour, the active match in a second colour, and scrolls to it.
Both colours are configured once at HtmlFrame construction time from ``cfg``.

``find_text("")`` clears all highlights.  The RendererProtocol exposes this
as ``find_text(term, index, ignore_case) -> int`` and ``clear_find()``.

Link routing
------------
  http:// / https://            → webbrowser.open()
  file:// + .md / .markdown     → on_navigate callback (open as new tab)
  file:// + no extension        → suppressed (bare dir URL from anchor resolution)
  file:// + other (.html, .png) → delegated to frame.load_url (anchor scroll, images)
  other                         → delegated to frame.load_url
"""
from __future__ import annotations

import tkinter as tk
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, runtime_checkable
from urllib.parse import unquote, urlparse


# ---------------------------------------------------------------------------
# URL helper
# ---------------------------------------------------------------------------
def _file_url_to_path(url: str) -> str | None:
    """
    Convert a ``file://`` URL to a local filesystem path, stripping any
    fragment.  Handles POSIX and Windows formats.
    Returns ``None`` for non-file URLs.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme != "file":
            return None
        path = unquote(parsed.path)
        if path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]   # Windows: /C:/path → C:/path
        return path
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------
@runtime_checkable
class RendererProtocol(Protocol):
    """
    Minimum interface any HTML renderer must satisfy.

    ``load_html``  — render in-memory HTML (welcome screen, error pages).
    ``load_url``   — render from a file:// URI; enables anchor navigation.
    ``find_text``  — highlight all matches, scroll to index-th; returns count.
    ``clear_find`` — remove all search highlights.
    ``get_widget`` — return the underlying tkinter widget for layout.
    """

    def load_html(self, html: str, base_url: str = "") -> None: ...
    def load_url(self, url: str) -> None: ...
    def find_text(self, term: str, index: int = 1,
                  ignore_case: bool = True) -> int: ...
    def clear_find(self) -> None: ...
    def get_widget(self) -> tk.Widget: ...


# ---------------------------------------------------------------------------
# tkinterweb adapter
# ---------------------------------------------------------------------------
class TkinterwebRenderer:
    """
    Renders HTML via a single tkinterweb.HtmlFrame.

    ``find_text`` delegates directly to tkinterweb's native
    ``HtmlFrame.find_text()``, which searches rendered text (not raw HTML),
    highlights all matches with ``cfg.find_match_color`` and the current
    match with ``cfg.find_current_color``, and scrolls to the selection.

    File management is not a responsibility of this class; ``TempHtmlStore``
    (owned by ``DocumentViewer``) handles all temp files.
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_navigate: Callable[[str], None] | None = None,
    ) -> None:
        from tkinterweb import HtmlFrame
        from config import cfg

        self._on_navigate = on_navigate
        self._frame: tk.Widget = HtmlFrame(
            parent,
            messages_enabled=False,
            vertical_scrollbar=True,
            on_link_click=self._handle_link_click,
            # Search highlight colours — configured once here from cfg
            find_match_highlight_color=cfg.find_match_color,
            find_match_text_color=cfg.find_match_text_color,
            find_current_highlight_color=cfg.find_current_color,
            find_current_text_color=cfg.find_current_text_color,
        )

    # ------------------------------------------------------------------
    def load_html(self, html: str, base_url: str = "") -> None:
        """Render in-memory HTML (welcome screen, error pages)."""
        try:
            self._frame.load_html(html, base_url=base_url)
        except TypeError:
            self._frame.load_html(html)

    def load_url(self, url: str) -> None:
        """Load from a file:// URI (per-tab temp file)."""
        self._frame.load_url(url)

    def find_text(
        self,
        term: str,
        index: int = 1,
        ignore_case: bool = True,
    ) -> int:
        """
        Highlight all occurrences of *term* in the rendered document and
        scroll to the *index*-th match (1-based).

        Returns the total number of matches.  Calling with an empty *term*
        clears all highlights (same as ``clear_find``).
        """
        return self._frame.find_text(
            term,
            select=index,
            ignore_case=ignore_case,
            highlight_all=True,
        )

    def clear_find(self) -> None:
        """Remove all search highlights from the rendered document."""
        self._frame.find_text("")

    def get_widget(self) -> tk.Widget:
        return self._frame

    # ------------------------------------------------------------------
    def _handle_link_click(self, url: str) -> None:
        """Called by tkinterweb for every user-initiated link click."""
        if not url:
            return

        if url.startswith(("http://", "https://")):
            webbrowser.open(url)
            return

        if url.startswith("file://"):
            local = _file_url_to_path(url)
            if local:
                p = Path(local)
                if not p.suffix:
                    return   # bare directory — suppress
                if p.suffix.lower() in (".md", ".markdown"):
                    if self._on_navigate:
                        self._on_navigate(local)
                    return
            self._frame.load_url(url)
            return

        self._frame.load_url(url)


# ---------------------------------------------------------------------------
# Plain-text fallback adapter
# ---------------------------------------------------------------------------
class ScrolledTextRenderer:
    """
    Plain-text fallback for when tkinterweb is unavailable.

    ``find_text`` and ``clear_find`` are stubs — text highlighting is not
    supported in this adapter.
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_navigate: Callable[[str], None] | None = None,
    ) -> None:
        import re
        from tkinter.scrolledtext import ScrolledText

        self._re     = re
        self._widget = ScrolledText(parent, wrap=tk.WORD, font=("Courier New", 11))

    def load_html(self, html: str, base_url: str = "") -> None:
        self._display(self._re.sub(r"<[^>]+>", "", html))

    def load_url(self, url: str) -> None:
        try:
            local = _file_url_to_path(url)
            if local:
                html = Path(local).read_text(encoding="utf-8")
                self.load_html(html)
        except Exception:
            pass

    def find_text(
        self,
        term: str,
        index: int = 1,
        ignore_case: bool = True,
    ) -> int:
        """Not supported in plain-text mode; always returns 0."""
        return 0

    def clear_find(self) -> None:
        """No-op in plain-text mode."""

    def get_widget(self) -> tk.Widget:
        return self._widget

    def _display(self, text: str) -> None:
        self._widget.config(state=tk.NORMAL)
        self._widget.delete("1.0", tk.END)
        self._widget.insert(tk.END, text)
        self._widget.config(state=tk.DISABLED)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def make_renderer(
    parent: tk.Widget,
    on_navigate: Callable[[str], None] | None = None,
) -> RendererProtocol:
    """
    Return the best available renderer for *parent*.

    *on_navigate* is called with a local filesystem path when the user
    clicks a link to a ``.md`` file inside the rendered content.
    """
    try:
        return TkinterwebRenderer(parent, on_navigate=on_navigate)
    except ImportError:
        from utils.logging_config import logger
        logger.warning("tkinterweb not available — using plain-text renderer")
        return ScrolledTextRenderer(parent, on_navigate=on_navigate)
