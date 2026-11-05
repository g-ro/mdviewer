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
# URL helper  (used by _handle_link_click and importable by temp_store)
# ---------------------------------------------------------------------------
def _file_url_to_path(url: str) -> str | None:
    """
    Convert a ``file://`` URL to a local filesystem path, stripping any
    fragment.  Handles both POSIX (``file:///home/…``) and Windows
    (``file:///C:/…``) formats.  Returns ``None`` for non-file URLs.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme != "file":
            return None
        path = unquote(parsed.path)
        # Windows: /C:/path → C:/path
        if path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]
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

    ``load_html`` — render in-memory HTML (welcome screen, error pages).
    ``load_url``  — render from a URL; enables anchor navigation.
    ``get_widget`` — return the underlying tkinter widget for layout.
    """

    def load_html(self, html: str, base_url: str = "") -> None: ...
    def load_url(self, url: str) -> None: ...
    def get_widget(self) -> tk.Widget: ...


# ---------------------------------------------------------------------------
# tkinterweb adapter
# ---------------------------------------------------------------------------
class TkinterwebRenderer:
    """
    Renders HTML via a single tkinterweb.HtmlFrame.

    Responsibilities
    ----------------
    * Display content via ``load_html`` or ``load_url``.
    * Intercept link clicks and route them appropriately.

    File management is NOT a responsibility of this class.
    ``TempHtmlStore`` (owned by ``DocumentViewer``) handles all temp files.
    This renderer simply receives a ``file://`` URI and loads it.
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_navigate: Callable[[str], None] | None = None,
    ) -> None:
        from tkinterweb import HtmlFrame

        self._on_navigate = on_navigate
        self._frame: tk.Widget = HtmlFrame(
            parent,
            messages_enabled=False,
            vertical_scrollbar=True,
            on_link_click=self._handle_link_click,
        )

    # ------------------------------------------------------------------
    def load_html(self, html: str, base_url: str = "") -> None:
        """
        Render *html* from a string.

        Use for content that does not require anchor navigation (welcome
        screen, inline error pages).  For actual documents, prefer
        ``load_url`` with a pre-written temp file so tkinterweb has a
        stable current URL.
        """
        try:
            self._frame.load_html(html, base_url=base_url)
        except TypeError:
            self._frame.load_html(html)

    def load_url(self, url: str) -> None:
        """
        Load from *url* (typically a ``file://`` pointing to a temp file).

        Because each tab has a unique URL, tkinterweb's cache is not an
        issue — different URL, different content.  No ``force=True`` needed.
        Anchor navigation works because tkinterweb has a stable current URL
        to resolve ``#section`` against.
        """
        self._frame.load_url(url)

    def get_widget(self) -> tk.Widget:
        return self._frame

    # ------------------------------------------------------------------
    def _handle_link_click(self, url: str) -> None:
        """Called by tkinterweb for every user-initiated link click."""
        if not url:
            return

        # External links → system browser
        if url.startswith(("http://", "https://")):
            webbrowser.open(url)
            return

        if url.startswith("file://"):
            local = _file_url_to_path(url)
            if local:
                p = Path(local)

                # No extension = bare directory path.
                # Arises from #anchor links resolved against a directory
                # base_url (safety net; should not normally occur now that
                # TempHtmlStore pre-processes HTML before writing).
                if not p.suffix:
                    return  # suppress silently

                # Cross-file .md link → open as new tab
                if p.suffix.lower() in (".md", ".markdown"):
                    if self._on_navigate:
                        self._on_navigate(local)
                    return

            # .html anchor navigation, images, CSS → delegate to frame
            self._frame.load_url(url)
            return

        self._frame.load_url(url)


# ---------------------------------------------------------------------------
# Plain-text fallback adapter
# ---------------------------------------------------------------------------
class ScrolledTextRenderer:
    """
    Plain-text fallback for when tkinterweb is unavailable.

    Strips HTML tags and displays the raw text.  ``load_url`` reads the
    file at the given ``file://`` URI and falls back to ``load_html``.
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
