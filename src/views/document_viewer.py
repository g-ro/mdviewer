#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tabbed document viewer — Eclipse-style overflow tabs.

Architecture
------------
``DocumentViewer`` is a thin coordinator:

  ``_TabBar``         — visual tab strip (no state knowledge)
  ``TabModel``        — all tab-state bookkeeping (pure Python, unit-testable)
  ``RendererProtocol``— HTML display abstraction (swap backend freely)
  ``TempHtmlStore``   — per-tab temp file lifecycle (stable URLs for tkinterweb)

Virtual tab list
----------------
Every opened file lives in the virtual tab list (via ``TabModel``).
The list is split into two tiers:

  VISIBLE  (up to ``cfg.max_tabs``): HTML held in memory + temp file on disk.
  OVERFLOW (unlimited):              Only file path stored; HTML and temp file
                                     discarded to free memory and disk space.

Temp file lifecycle
-------------------
  Tab becomes VISIBLE   → TempHtmlStore.write(tab_id, html, base_url)
  Tab stays  VISIBLE    → renderer.load_url(store.uri_for(tab_id))
  Tab becomes OVERFLOW  → TempHtmlStore.release(tab_id)
  Tab is CLOSED         → TempHtmlStore.release(tab_id)
  Process exits         → TempHtmlStore.cleanup_all()  [via atexit]
"""
from __future__ import annotations

import html as html_module
import uuid
import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable

from config import cfg
from models.tab_model import TabData, TabModel
from utils.logging_config import logger
from utils.md_converter import convert_md_to_html
from utils.renderer import RendererProtocol, make_renderer
from utils.temp_store import TempHtmlStore

_WELCOME_HTML = """\
<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       display:flex; align-items:center; justify-content:center;
       height:100vh; margin:0; background:#f6f8fa; color:#586069; }
.box { text-align:center; }
.box h2  { font-size:1.6em; color:#24292e; margin-bottom:8px; }
.box p   { font-size:1em; margin:4px 0; }
.box kbd { background:#eaecef; border:1px solid #d1d5da; border-radius:3px;
           padding:2px 6px; font-family:monospace; font-size:.9em; }
</style></head><body>
<div class="box">
  <h2>&#128221; MDViewer</h2>
  <p>Double-click a <strong>.md</strong> file in the explorer,</p>
  <p>or use <kbd>Ctrl+O</kbd> to open a file directly.</p>
</div></body></html>"""


# ---------------------------------------------------------------------------
# Tab bar widget (visual only — no state knowledge)
# ---------------------------------------------------------------------------
@dataclass
class _TabEntry:
    """Typed widget container for one tab button."""
    tab_id: str
    title:  str
    outer:  tk.Frame
    lbl:    tk.Label
    close:  tk.Label


class _TabBar(ttk.Frame):
    """
    Horizontal strip of closeable tab buttons.

    Owns only the visual state (widgets + which tab is highlighted).
    All semantic state lives in ``TabModel``.
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_select: Callable[[str], None],
        on_close:  Callable[[str], None],
    ) -> None:
        super().__init__(parent, relief=tk.FLAT)
        self._on_select            = on_select
        self._on_close             = on_close
        self._tabs: list[_TabEntry] = []
        self.active_id: str | None  = None

        self._inner = tk.Frame(self, bg=cfg.tab_bar_background)
        self._inner.pack(fill=tk.BOTH, expand=True, pady=(2, 0))

    def add(self, tab_id: str, title: str) -> None:
        outer = tk.Frame(self._inner, bg=cfg.tab_color_inactive,
                         bd=1, relief=tk.RAISED)
        outer.pack(side=tk.LEFT, padx=(2, 0))

        lbl = tk.Label(outer, text=f"  {title}  ",
                       bg=cfg.tab_color_inactive, cursor="hand2", pady=4)
        lbl.pack(side=tk.LEFT)

        close_lbl = tk.Label(outer, text=" × ", bg=cfg.tab_color_inactive,
                             fg="#666", cursor="hand2", pady=4)
        close_lbl.pack(side=tk.LEFT)

        entry = _TabEntry(tab_id=tab_id, title=title,
                          outer=outer, lbl=lbl, close=close_lbl)

        for w in (outer, lbl):
            w.bind("<Button-1>", lambda _e, tid=tab_id: self._on_select(tid))
            w.bind("<Button-2>", lambda _e, tid=tab_id: self._on_close(tid))
        close_lbl.bind("<Button-1>", lambda _e, tid=tab_id: self._on_close(tid))
        close_lbl.bind("<Button-2>", lambda _e, tid=tab_id: self._on_close(tid))

        for w in (outer, lbl, close_lbl):
            w.bind("<Enter>", lambda _e, eid=tab_id: self._on_hover(eid, True))
            w.bind("<Leave>", lambda _e, eid=tab_id: self._on_hover(eid, False))

        self._tabs.append(entry)
        self._highlight(tab_id)

    def select(self, tab_id: str) -> None:
        self._highlight(tab_id)

    def remove(self, tab_id: str) -> str | None:
        """Destroy the tab widget; returns the tab_id that now follows it."""
        idx = next((i for i, t in enumerate(self._tabs) if t.tab_id == tab_id), None)
        if idx is None:
            return None
        self._tabs[idx].outer.destroy()
        self._tabs.pop(idx)
        if not self._tabs:
            self.active_id = None
            return None
        successor = self._tabs[min(idx, len(self._tabs) - 1)].tab_id
        self._highlight(successor)
        return successor

    def count(self) -> int:
        return len(self._tabs)

    def _highlight(self, tab_id: str) -> None:
        self.active_id = tab_id
        for t in self._tabs:
            color = cfg.tab_color_active if t.tab_id == tab_id else cfg.tab_color_inactive
            for w in (t.outer, t.lbl, t.close):
                w.configure(bg=color)

    def _on_hover(self, tab_id: str, entering: bool) -> None:
        if tab_id == self.active_id:
            return
        color = cfg.tab_color_hover if entering else cfg.tab_color_inactive
        entry = next((t for t in self._tabs if t.tab_id == tab_id), None)
        if entry:
            for w in (entry.outer, entry.lbl, entry.close):
                w.configure(bg=color)


# ---------------------------------------------------------------------------
# Document viewer
# ---------------------------------------------------------------------------
class DocumentViewer(ttk.Frame):
    """
    Tabbed document viewer.

    Coordinates four collaborators:
      ``TabModel``      — tab-state (visible / overflow tiers)
      ``_TabBar``       — visual tab strip
      ``RendererProtocol`` — HTML display widget
      ``TempHtmlStore`` — per-tab temp file lifecycle

    ``on_status_update`` is injected at construction (not set post-hoc) so
    the dependency is explicit and the class is self-contained from init.
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_status_update: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._model            = TabModel(max_visible=cfg.max_tabs)
        self._temp_store       = TempHtmlStore()
        self._on_status_update = on_status_update
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # ── Toolbar ──────────────────────────────────────────────────
        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        ttk.Button(toolbar, text="↺  Refresh",
                   command=self.refresh_current_tab).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(toolbar, text="✕  Close Tab",
                   command=self.close_current_tab).pack(side=tk.LEFT)

        # ── Tab row: strip + overflow button ─────────────────────────
        tab_row = ttk.Frame(self)
        tab_row.grid(row=1, column=0, sticky="ew")
        tab_row.columnconfigure(0, weight=1)
        tab_row.columnconfigure(1, weight=0)

        self._tab_bar = _TabBar(tab_row,
                                on_select=self._select_visible,
                                on_close=self._close_visible)
        self._tab_bar.grid(row=0, column=0, sticky="ew")

        self._ovf_btn = tk.Button(
            tab_row, text="»  0", width=6,
            command=self._show_overflow_menu,
            relief=tk.FLAT, bg=cfg.tab_bar_background, fg="#222",
            font=("", 9, "bold"), cursor="hand2",
        )
        self._ovf_btn.grid(row=0, column=1, padx=(2, 0), pady=(2, 0))
        self._ovf_btn.grid_remove()

        # ── Single renderer ───────────────────────────────────────────
        content = ttk.Frame(self)
        content.grid(row=2, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        self._renderer: RendererProtocol = make_renderer(
            content,
            on_navigate=self._on_renderer_navigate,
        )
        self._renderer.get_widget().grid(row=0, column=0, sticky="nsew")

        self._render_welcome()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def open_file(self, file_path: str) -> None:
        """Open *file_path*: switch/promote if already known, else load fresh."""
        path = str(Path(file_path).resolve())

        if self._model.is_open(path):
            tab_id = self._model.tab_id_for(path)
            if self._model.is_visible(tab_id):
                self._select_visible(tab_id)
            else:
                self._promote(tab_id)
            return

        html, base_url = self._render_file(path)
        tab_id = str(uuid.uuid4())
        data   = TabData(tab_id=tab_id, file_path=path,
                         html=html, base_url=base_url)

        demoted_id = self._model.add_visible(data)
        if demoted_id:
            self._tab_bar.remove(demoted_id)
            self._temp_store.release(demoted_id)       # free demoted tab's file
            demoted_name = Path(
                self._model.get_overflow_path(demoted_id) or ""
            ).name
            self._notify(
                f'"{demoted_name}" moved to overflow  —  click » to bring it back'
            )

        # Write temp file and load via stable file URI
        self._temp_store.write(tab_id, html, base_url)
        self._tab_bar.add(tab_id, Path(path).name)
        self._renderer.load_url(self._temp_store.uri_for(tab_id))
        self._update_overflow_btn()

    def close_current_tab(self) -> None:
        if self._tab_bar.active_id:
            self._close_visible(self._tab_bar.active_id)

    def refresh_current_tab(self) -> None:
        tab_id = self._tab_bar.active_id
        if not tab_id or not self._model.is_visible(tab_id):
            return
        data = self._model.get_visible(tab_id)
        if not data:
            return
        html, base_url = self._render_file(data.file_path)
        self._model.update_visible_html(tab_id, html, base_url)
        # Overwrite the existing temp file and reload
        self._temp_store.write(tab_id, html, base_url)
        self._renderer.load_url(self._temp_store.uri_for(tab_id))

    # ------------------------------------------------------------------
    # Visible-tab callbacks (wired to _TabBar)
    # ------------------------------------------------------------------
    def _select_visible(self, tab_id: str) -> None:
        self._tab_bar.select(tab_id)
        if self._model.is_visible(tab_id):
            # Each tab has its own stable URI — no force, no caching issue
            self._renderer.load_url(self._temp_store.uri_for(tab_id))

    def _close_visible(self, tab_id: str) -> None:
        """
        Close a visible tab.  Auto-promotes the most-recently-parked
        overflow tab if one exists.
        """
        auto_promote_id = self._model.close_visible(tab_id)
        successor       = self._tab_bar.remove(tab_id)
        self._temp_store.release(tab_id)               # delete the closed tab's file

        if auto_promote_id:
            self._promote(auto_promote_id)
            return

        self._update_overflow_btn()
        if self._model.visible_count > 0 and successor:
            self._select_visible(successor)
        elif self._model.visible_count > 0 and self._tab_bar.active_id:
            self._select_visible(self._tab_bar.active_id)
        else:
            self._render_welcome()

    # ------------------------------------------------------------------
    # Overflow helpers
    # ------------------------------------------------------------------
    def _promote(self, tab_id: str) -> None:
        """Reload a parked tab from disk, write its temp file, make it active."""
        file_path = self._model.get_overflow_path(tab_id)
        if not file_path:
            return

        html, base_url = self._render_file(file_path)
        demoted_id = self._model.promote(tab_id, html, base_url)

        if demoted_id:
            self._tab_bar.remove(demoted_id)
            self._temp_store.release(demoted_id)       # free the demoted tab's file
            demoted_name = Path(
                self._model.get_overflow_path(demoted_id) or ""
            ).name
            self._notify(f'"{demoted_name}" moved to overflow')

        # Write temp file for the promoted tab and display it
        self._temp_store.write(tab_id, html, base_url)
        self._tab_bar.add(tab_id, Path(file_path).name)
        self._renderer.load_url(self._temp_store.uri_for(tab_id))
        self._update_overflow_btn()

    def _show_overflow_menu(self) -> None:
        items = self._model.overflow_items
        if not items:
            return
        menu = tk.Menu(self, tearoff=0)
        for tab_id, file_path in items:
            p = Path(file_path)
            menu.add_command(
                label=f"  {p.name}   ({p.parent})",
                command=lambda tid=tab_id: self._promote(tid),
            )
        if len(items) > 1:
            menu.add_separator()
            menu.add_command(label="  Close all hidden tabs",
                             command=self._close_all_overflow)

        btn = self._ovf_btn
        menu.tk_popup(btn.winfo_rootx(),
                      btn.winfo_rooty() + btn.winfo_height())

    def _close_all_overflow(self) -> None:
        # Overflow tabs have no temp files (released when they were demoted)
        self._model.close_all_overflow()
        self._update_overflow_btn()

    def _update_overflow_btn(self) -> None:
        n = self._model.overflow_count
        if n:
            self._ovf_btn.configure(text=f"»  {n}")
            self._ovf_btn.grid()
        else:
            self._ovf_btn.grid_remove()

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _render_file(self, file_path: str) -> tuple[str, str]:
        """Convert a Markdown file to (html, base_url). Never raises."""
        try:
            html     = convert_md_to_html(file_path)
            base_url = Path(file_path).parent.as_uri() + "/"
        except Exception as exc:
            logger.exception("Failed to render %s", file_path)
            safe_msg = html_module.escape(str(exc))
            html     = (
                f'<p style="color:red;font-family:sans-serif">'
                f"Error loading file:<br>{safe_msg}</p>"
            )
            base_url = ""
        return html, base_url

    def _render_welcome(self) -> None:
        # Welcome screen has no links needing anchor navigation;
        # load_html is fine and avoids writing an unnecessary temp file.
        self._renderer.load_html(_WELCOME_HTML, "")

    def _on_renderer_navigate(self, local_path: str) -> None:
        """Called when the user clicks a local .md link inside rendered content."""
        self.open_file(local_path)

    def _notify(self, message: str) -> None:
        if self._on_status_update:
            self._on_status_update(message)
