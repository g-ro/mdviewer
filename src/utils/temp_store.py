#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Temporary HTML file store — per-tab lifecycle management.

``TempHtmlStore`` is the single owner of the ``%TEMP%/mdviewer/`` directory.
Every visible tab has exactly one file in that directory, named by its UUID.
This gives tkinterweb a **stable, unique URL** per tab, which:

  * eliminates the need for ``force=True`` (different URLs → no cache collision)
  * enables in-document anchor navigation (tkinterweb has a real current URL)
  * isolates concurrent MDViewer instances (each tab UUID is globally unique)

Lifecycle
---------
  write(key, html, base_url)   called when a tab becomes visible (open/promote)
  release(key)                 called when a tab becomes invisible (close/demote)
  cleanup_all()                called on process exit (registered via atexit)
  _sweep_stale()               called on init to remove orphans from crashed runs

Thread safety
-------------
Not required.  The application runs on the Tkinter single-threaded event loop;
all calls originate from that thread.
"""
from __future__ import annotations

import atexit
import re
import tempfile
import time
from pathlib import Path
from typing import ClassVar
from urllib.parse import urljoin

from utils.logging_config import logger

# ---------------------------------------------------------------------------
# URL pre-processing helper  (moved here from renderer.py)
# ---------------------------------------------------------------------------
_ATTR_RE = re.compile(r'(src|href)\s*=\s*(["\'])([^"\']*?)\2', re.IGNORECASE)


def _make_urls_absolute(html: str, base_url: str) -> str:
    """
    Rewrite every relative ``src`` / ``href`` in *html* to an absolute URL
    resolved against *base_url*.

    Leaves unchanged: anchors (``#``), external (``http/https``), ``data:``,
    ``mailto:``, and anything already absolute (``file://``).
    """
    def _replace(m: re.Match) -> str:
        attr, quote, url = m.group(1), m.group(2), m.group(3)
        if not url or url.startswith(
            ("#", "http://", "https://", "data:", "file://", "mailto://", "mailto:")
        ):
            return m.group(0)
        return f'{attr}={quote}{urljoin(base_url, url)}{quote}'

    return _ATTR_RE.sub(_replace, html)


# ---------------------------------------------------------------------------
# TempHtmlStore
# ---------------------------------------------------------------------------
class TempHtmlStore:
    """
    Manages per-key temporary HTML files under ``%TEMP%/mdviewer/``.

    Typical usage from ``DocumentViewer``::

        store = TempHtmlStore()

        # When a tab is made visible:
        store.write(tab_id, html, base_url)
        renderer.load_url(store.uri_for(tab_id))

        # When a tab is closed or demoted:
        store.release(tab_id)

    ``cleanup_all`` is registered with ``atexit`` at construction time so
    temp files are removed on normal process exit.  ``_sweep_stale`` runs
    at construction time to remove files left by a previous crashed session.
    """

    DIR_NAME:       ClassVar[str] = "mdviewer"
    STALE_HOURS:    ClassVar[int] = 24

    def __init__(self) -> None:
        self._dir = Path(tempfile.gettempdir()) / self.DIR_NAME
        self._ensure_dir()
        self._sweep_stale()
        atexit.register(self.cleanup_all)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def write(self, key: str, html: str, base_url: str = "") -> Path:
        """
        Pre-process *html* and write it to the temp file for *key*.

        If *base_url* is provided, relative ``src``/``href`` attributes are
        rewritten to absolute ``file://`` URLs before writing so that images
        and other relative resources resolve correctly from the temp location.
        Anchor links (``#section``) are intentionally left unchanged so they
        resolve against the temp file's own URL, enabling in-document scroll.

        Returns the ``Path`` of the written file.
        """
        if base_url:
            html = _make_urls_absolute(html, base_url)
        path = self._path_for(key)
        try:
            path.write_text(html, encoding="utf-8")
        except OSError as exc:
            logger.error("TempHtmlStore: could not write file for key %r: %s", key, exc)
            raise
        return path

    def uri_for(self, key: str) -> str:
        """Return the ``file://`` URI for *key*'s temp file."""
        return self._path_for(key).as_uri()

    def release(self, key: str) -> None:
        """
        Delete the temp file for *key*.

        Safe to call if the file does not exist (e.g. after a failed write).
        """
        path = self._path_for(key)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning(
                "TempHtmlStore: could not delete file for key %r: %s", key, exc
            )

    def cleanup_all(self) -> None:
        """
        Delete every ``*.html`` file in the store directory.

        Registered with ``atexit`` at construction time.  Also callable
        explicitly for testing.
        """
        try:
            for f in self._dir.glob("*.html"):
                try:
                    f.unlink(missing_ok=True)
                except OSError:
                    pass
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _path_for(self, key: str) -> Path:
        """Return the ``Path`` for *key*'s temp file (may not yet exist)."""
        return self._dir / f"{key}.html"

    def _ensure_dir(self) -> None:
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.error("TempHtmlStore: cannot create temp directory %s: %s",
                         self._dir, exc)
            raise

    def _sweep_stale(self) -> None:
        """Remove ``*.html`` files older than ``STALE_HOURS`` hours."""
        cutoff = time.time() - (self.STALE_HOURS * 3600)
        try:
            for f in self._dir.glob("*.html"):
                try:
                    if f.stat().st_mtime < cutoff:
                        f.unlink(missing_ok=True)
                except OSError:
                    pass
        except OSError:
            pass
