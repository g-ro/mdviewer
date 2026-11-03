#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Renderer abstraction layer.

Defines ``RendererProtocol`` and two concrete adapters:
  ``TkinterwebRenderer``   — full HTML + CSS via tkinterweb.HtmlFrame
  ``ScrolledTextRenderer`` — plain-text fallback when tkinterweb is absent

Use ``make_renderer(parent, on_navigate)`` to get the best available renderer.

How anchor navigation works
----------------------------
tkinterweb resolves relative links against a "current URL".  When we use
``load_html()`` directly, there is no current URL, so ``#section`` anchors
have nowhere to resolve to.

Instead we:
  1. Pre-process the HTML, rewriting every relative ``src``/``href`` to an
     absolute ``file://`` URL using the original file's directory as base.
     This preserves images, cross-file links, etc.
  2. Write the processed HTML to a temp file.
  3. Load the temp file via ``load_url()``.

Now ``<a href="#section">`` resolves to ``file:///tmp/render.html#section``.
tkinterweb calls our ``on_link_click`` handler with that URL; we see the
``.html`` extension, pass it back to ``load_url``, and tkinterweb scrolls to
the anchor — exactly as a browser would.

Link routing table
------------------
  http:// / https://          → webbrowser.open()
  file:// + .md / .markdown   → on_navigate callback (new tab)
  file:// + no extension      → suppressed (bare dir URL, safety net)
  file:// + anything else     → load_url (images, CSS, .html with anchor)
  other                       → load_url
"""
from __future__ import annotations

import re
import tempfile
import tkinter as tk
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, runtime_checkable
from urllib.parse import unquote, urljoin, urlparse


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

# Matches src="..." and href="..." (single or double quotes)
_ATTR_RE = re.compile(r'(src|href)\s*=\s*(["\'])([^"\']*?)\2', re.IGNORECASE)


def _make_urls_absolute(html: str, base_url: str) -> str:
    """
    Rewrite every relative ``src`` / ``href`` value in *html* to an absolute
    URL by resolving it against *base_url*.

    Leaves unchanged: anchors (``#``), external URLs, ``data:`` URIs,
    ``mailto:``, and anything already absolute (``file://``, ``http://``).
    """
    def _replace(m: re.Match) -> str:
        attr, quote, url = m.group(1), m.group(2), m.group(3)
        if not url or url.startswith(
            ("#", "http://", "https://", "data:", "file://", "mailto://", "mailto:")
        ):
            return m.group(0)
        return f'{attr}={quote}{urljoin(base_url, url)}{quote}'

    return _ATTR_RE.sub(_replace, html)


def _file_url_to_path(url: str) -> str | None:
    """
    Convert a ``file://`` URL to a local path, stripping any fragment.
    Handles POSIX and Windows (``file:///C:/…``) formats.
    Returns ``None`` if *url* is not a ``file://`` URL.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme != "file":
            return None
        path = unquote(parsed.path)          # strips fragment automatically
        if path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]                  # Windows: /C:/… → C:/…
        return path
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------
@runtime_checkable
class RendererProtocol(Protocol):
    """Minimal contract any HTML renderer must satisfy."""

    def load_html(self, html: str, base_url: str = "") -> None: ...
    def get_widget(self) -> tk.Widget: ...


# ---------------------------------------------------------------------------
# tkinterweb adapter
# ---------------------------------------------------------------------------
class TkinterwebRenderer:
    """
    Renders HTML + CSS via a single tkinterweb.HtmlFrame.

    See module docstring for the full explanation of the temp-file strategy
    that makes anchor navigation work correctly.
    """

    _TEMP_FILE: Path | None = None   # shared across all instances

    def __init__(
        self,
        parent: tk.Widget,
        on_navigate: Callable[[str], None] | None = None,
    ) -> None:
        from tkinterweb import HtmlFrame

        self._on_navigate = on_navigate

        # One shared temp file for the lifetime of the process
        if TkinterwebRenderer._TEMP_FILE is None:
            tmp = Path(tempfile.gettempdir()) / "mdviewer_render"
            tmp.mkdir(parents=True, exist_ok=True)
            TkinterwebRenderer._TEMP_FILE = tmp / "current.html"

        self._frame: tk.Widget = HtmlFrame(
            parent,
            messages_enabled=False,
            vertical_scrollbar=True,
            on_link_click=self._handle_link_click,
        )

    # ------------------------------------------------------------------
    def load_html(self, html: str, base_url: str = "") -> None:
        """
        Render *html*.

        If *base_url* is provided, relative URLs in the HTML are first
        rewritten to absolute ``file://`` URLs; then the processed HTML is
        written to a temp file and loaded via ``load_url`` so tkinterweb has
        a known current URL — which is required for ``#anchor`` navigation.
        """
        if base_url:
            html = _make_urls_absolute(html, base_url)

        try:
            assert self._TEMP_FILE is not None
            self._TEMP_FILE.write_text(html, encoding="utf-8")
            self._frame.load_url(self._TEMP_FILE.as_uri())
        except Exception:
            # Fallback if temp file write fails (e.g. permission error)
            try:
                self._frame.load_html(html, base_url=base_url)
            except TypeError:
                self._frame.load_html(html)

    def get_widget(self) -> tk.Widget:
        return self._frame

    # ------------------------------------------------------------------
    def _handle_link_click(self, url: str) -> None:
        """Called by tkinterweb for every user link click."""
        if not url:
            return

        # External → system browser
        if url.startswith(("http://", "https://")):
            webbrowser.open(url)
            return

        if url.startswith("file://"):
            local = _file_url_to_path(url)
            if local:
                p = Path(local)
                if not p.suffix:
                    return   # bare directory path — suppress silently

                if p.suffix.lower() in (".md", ".markdown"):
                    if self._on_navigate:
                        self._on_navigate(local)
                    return

            # .html anchor nav, images, CSS — let tkinterweb handle
            self._frame.load_url(url)
            return

        self._frame.load_url(url)


# ---------------------------------------------------------------------------
# Plain-text fallback adapter
# ---------------------------------------------------------------------------
class ScrolledTextRenderer:
    """Plain-text fallback: strips HTML tags, displays raw text."""

    def __init__(
        self,
        parent: tk.Widget,
        on_navigate: Callable[[str], None] | None = None,
    ) -> None:
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
    clicks a link to a ``.md`` file.
    """
    try:
        return TkinterwebRenderer(parent, on_navigate=on_navigate)
    except ImportError:
        from utils.logging_config import logger
        logger.warning("tkinterweb not available — using plain-text renderer")
        return ScrolledTextRenderer(parent, on_navigate=on_navigate)
