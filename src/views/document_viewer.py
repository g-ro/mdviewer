#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tabbed document viewer — Eclipse-style overflow tabs.

Virtual tab list
----------------
Every opened file lives in the *virtual* tab list (just a file path — cheap).
The list is split into two tiers:

  VISIBLE  (up to MAX_TABS):  HTML is loaded and held in memory.
  OVERFLOW (unlimited):       Only the file path is stored.

The tab bar shows only visible tabs plus a "» N" overflow button when N > 0.
Clicking the button shows a menu of hidden tab names.
Selecting a hidden tab *promotes* it to visible (reloads from disk) and
*demotes* the oldest visible tab to overflow (HTML discarded).

Closing a visible tab with × removes it entirely (path freed) and, if there
are overflow tabs, promotes the most-recently-parked one automatically.

Single HtmlFrame
----------------
Only one HtmlFrame widget exists for the lifetime of the window.
Switching between visible tabs simply calls load_html() with the stored HTML.
This avoids the tkinterweb crash that occurs with multiple simultaneous
HtmlFrame instances.
"""
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import uuid
from collections import OrderedDict

from utils.logging_config import logger
from utils.md_converter import convert_md_to_html

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MAX_TABS: int = 5   # Max simultaneously *visible* (rendered) tabs. 0 = no limit.

try:
    from tkinterweb import HtmlFrame
    _TKINTERWEB_AVAILABLE = True
except ImportError:
    _TKINTERWEB_AVAILABLE = False
    logger.warning("tkinterweb not available — falling back to plain-text viewer")

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
# Tab bar widget  (visible tabs only)
# ---------------------------------------------------------------------------
class _TabBar(ttk.Frame):
    """Horizontal strip of closeable tab buttons for *visible* tabs only."""

    _ACTIVE   = "#ffffff"
    _INACTIVE = "#d0d0d0"
    _HOVER    = "#ebebeb"

    def __init__(self, parent: tk.Widget, on_select, on_close):
        super().__init__(parent, relief=tk.FLAT)
        self._on_select = on_select
        self._on_close  = on_close
        self._tabs: list[dict] = []
        self.active_id: str | None = None

        self._inner = tk.Frame(self, bg="#b8b8b8")
        self._inner.pack(fill=tk.BOTH, expand=True, pady=(2, 0))

    # ------------------------------------------------------------------
    def add(self, tab_id: str, title: str) -> None:
        outer = tk.Frame(self._inner, bg=self._INACTIVE, bd=1, relief=tk.RAISED)
        outer.pack(side=tk.LEFT, padx=(2, 0))

        lbl = tk.Label(outer, text=f"  {title}  ",
                       bg=self._INACTIVE, cursor="hand2", pady=4)
        lbl.pack(side=tk.LEFT)

        close_lbl = tk.Label(outer, text=" × ", bg=self._INACTIVE,
                             fg="#666", cursor="hand2", pady=4)
        close_lbl.pack(side=tk.LEFT)

        for w in (outer, lbl):
            w.bind("<Button-1>", lambda _e, tid=tab_id: self._on_select(tid))
            w.bind("<Button-2>", lambda _e, tid=tab_id: self._on_close(tid))
        close_lbl.bind("<Button-1>", lambda _e, tid=tab_id: self._on_close(tid))
        close_lbl.bind("<Button-2>", lambda _e, tid=tab_id: self._on_close(tid))

        self._tabs.append({"id": tab_id, "title": title,
                           "outer": outer, "lbl": lbl, "close": close_lbl})
        self._highlight(tab_id)

    def select(self, tab_id: str) -> None:
        self._highlight(tab_id)

    def remove(self, tab_id: str) -> str | None:
        """Destroy the tab widget. Returns the tab_id that visually follows it."""
        idx = next((i for i, t in enumerate(self._tabs) if t["id"] == tab_id), None)
        if idx is None:
            return None
        self._tabs[idx]["outer"].destroy()
        self._tabs.pop(idx)
        if not self._tabs:
            self.active_id = None
            return None
        successor = self._tabs[min(idx, len(self._tabs) - 1)]["id"]
        self._highlight(successor)
        return successor

    def count(self) -> int:
        return len(self._tabs)

    def _highlight(self, tab_id: str) -> None:
        self.active_id = tab_id
        for t in self._tabs:
            color = self._ACTIVE if t["id"] == tab_id else self._INACTIVE
            for w in (t["outer"], t["lbl"], t["close"]):
                w.configure(bg=color)


# ---------------------------------------------------------------------------
# Document viewer
# ---------------------------------------------------------------------------
class DocumentViewer(ttk.Frame):
    """
    Tabbed viewer with Eclipse-style overflow tabs and a single HtmlFrame.

    _vis  — OrderedDict[tab_id, {file_path, html, base_url}]
              Visible tabs, oldest-first (front = demote candidate).

    _ovf  — OrderedDict[tab_id, file_path]
              Overflow (parked) tabs, oldest-first (front = auto-promote candidate).
              Only file paths are stored here — no HTML in memory.

    _path_tab — dict[file_path, tab_id]
              Reverse lookup that spans both tiers.
    """

    def __init__(self, parent: tk.Widget):
        super().__init__(parent)
        self._vis:      OrderedDict[str, dict] = OrderedDict()
        self._ovf:      OrderedDict[str, str]  = OrderedDict()
        self._path_tab: dict[str, str]          = {}

        # Injected by MainWindow
        self.on_status_update = None   # (msg: str) -> None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
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
        tab_row.columnconfigure(0, weight=1)   # tab strip grows
        tab_row.columnconfigure(1, weight=0)   # overflow button fixed

        self._tab_bar = _TabBar(tab_row,
                                on_select=self._select_visible,
                                on_close=self._close_visible)
        self._tab_bar.grid(row=0, column=0, sticky="ew")

        self._ovf_btn = tk.Button(
            tab_row, text="»  0", width=6,
            command=self._show_overflow_menu,
            relief=tk.FLAT, bg="#b8b8b8", fg="#222",
            font=("", 9, "bold"), cursor="hand2",
        )
        self._ovf_btn.grid(row=0, column=1, padx=(2, 0), pady=(2, 0))
        self._ovf_btn.grid_remove()   # hidden until there is overflow

        # ── Single HtmlFrame ─────────────────────────────────────────
        content = ttk.Frame(self)
        content.grid(row=2, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        if _TKINTERWEB_AVAILABLE:
            self._renderer = HtmlFrame(content, messages_enabled=False,
                                       vertical_scrollbar=True)
        else:
            from tkinter.scrolledtext import ScrolledText
            self._renderer = ScrolledText(content, wrap=tk.WORD,
                                          font=("Courier New", 11))
        self._renderer.grid(row=0, column=0, sticky="nsew")

        self._render_welcome()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def open_file(self, file_path: str) -> None:
        """Open *file_path*, promoting it if it's already parked in overflow."""
        path = str(Path(file_path).resolve())

        if path in self._path_tab:
            tab_id = self._path_tab[path]
            if tab_id in self._vis:
                self._select_visible(tab_id)          # already visible
            else:
                self._promote(tab_id)                 # parked → front
            return

        # Brand-new file
        if MAX_TABS > 0 and self._tab_bar.count() >= MAX_TABS:
            self._demote_oldest_visible()

        tab_id = str(uuid.uuid4())
        html, base_url = self._render_file(path)
        self._vis[tab_id]      = {"file_path": path, "html": html, "base_url": base_url}
        self._path_tab[path]   = tab_id
        self._tab_bar.add(tab_id, Path(path).name)
        self._load(html, base_url)

    def close_current_tab(self) -> None:
        tab_id = self._tab_bar.active_id
        if tab_id:
            self._close_visible(tab_id)

    def refresh_current_tab(self) -> None:
        tab_id = self._tab_bar.active_id
        if not tab_id or tab_id not in self._vis:
            return
        data = self._vis[tab_id]
        data["html"], data["base_url"] = self._render_file(data["file_path"])
        self._load(data["html"], data["base_url"])

    # ------------------------------------------------------------------
    # Visible-tab callbacks (wired to _TabBar)
    # ------------------------------------------------------------------
    def _select_visible(self, tab_id: str) -> None:
        self._tab_bar.select(tab_id)
        if tab_id in self._vis:
            d = self._vis[tab_id]
            self._load(d["html"], d["base_url"])

    def _close_visible(self, tab_id: str) -> None:
        """
        Close a visible tab.
        If overflow tabs exist, the most-recently-parked one is auto-promoted
        (fills the vacated slot), keeping the tab bar as full as possible.
        """
        data = self._vis.pop(tab_id, None)
        if data:
            self._path_tab.pop(data["file_path"], None)

        successor = self._tab_bar.remove(tab_id)   # visual removal

        # Auto-promote the most-recently-parked overflow tab (last in _ovf)
        if self._ovf:
            promote_id = next(reversed(self._ovf))  # most recently parked
            self._promote(promote_id, after_close=True)
            return   # _promote handles rendering and overflow btn update

        self._update_overflow_btn()

        if successor:
            self._select_visible(successor)
        elif self._vis:
            # successor might be stale; select whatever is still active
            self._select_visible(self._tab_bar.active_id)
        else:
            self._render_welcome()

    # ------------------------------------------------------------------
    # Demote / promote
    # ------------------------------------------------------------------
    def _demote_oldest_visible(self) -> None:
        """
        Move the oldest visible tab to overflow (discard its HTML).
        Does NOT update the renderer — caller is responsible for that.
        """
        oldest_id = next(iter(self._vis))
        data = self._vis.pop(oldest_id)
        self._ovf[oldest_id] = data["file_path"]  # keep only path
        self._tab_bar.remove(oldest_id)            # visual only
        self._update_overflow_btn()

        name = Path(data["file_path"]).name
        if self.on_status_update:
            self.on_status_update(
                f'"{name}" moved to overflow  —  click » to bring it back'
            )

    def _promote(self, tab_id: str, *, after_close: bool = False) -> None:
        """
        Move an overflow tab to the front (visible).
        Reloads the file from disk.
        If visible slots are full and this isn't called after a close, demote first.
        """
        file_path = self._ovf.pop(tab_id)

        if not after_close and MAX_TABS > 0 and self._tab_bar.count() >= MAX_TABS:
            self._demote_oldest_visible()

        html, base_url = self._render_file(file_path)
        self._vis[tab_id] = {"file_path": file_path, "html": html, "base_url": base_url}
        # _path_tab entry already exists (tab_id was registered when first opened)

        self._tab_bar.add(tab_id, Path(file_path).name)
        self._load(html, base_url)
        self._update_overflow_btn()

    # ------------------------------------------------------------------
    # Overflow menu
    # ------------------------------------------------------------------
    def _show_overflow_menu(self) -> None:
        if not self._ovf:
            return
        menu = tk.Menu(self, tearoff=0)
        for tab_id, file_path in reversed(self._ovf.items()):
            p = Path(file_path)
            # Show filename bold + dimmed parent path
            menu.add_command(
                label=f"  {p.name}   ({p.parent})",
                command=lambda tid=tab_id: self._promote(tid),
            )
        if len(self._ovf) > 1:
            menu.add_separator()
            menu.add_command(label="  Close all hidden tabs",
                             command=self._close_all_overflow)

        btn = self._ovf_btn
        menu.tk_popup(btn.winfo_rootx(),
                      btn.winfo_rooty() + btn.winfo_height())

    def _close_all_overflow(self) -> None:
        for file_path in list(self._ovf.values()):
            self._path_tab.pop(file_path, None)
        self._ovf.clear()
        self._update_overflow_btn()

    def _update_overflow_btn(self) -> None:
        n = len(self._ovf)
        if n:
            self._ovf_btn.configure(text=f"»  {n}")
            self._ovf_btn.grid()
        else:
            self._ovf_btn.grid_remove()

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _render_file(self, file_path: str) -> tuple[str, str]:
        """Return (html, base_url) for *file_path*. Never raises."""
        try:
            html     = convert_md_to_html(file_path)
            base_url = Path(file_path).parent.as_uri() + "/"
        except Exception as exc:
            logger.exception("Failed to render %s", file_path)
            html     = (f'<p style="color:red;font-family:sans-serif">'
                        f'Error loading file:<br>{exc}</p>')
            base_url = ""
        return html, base_url

    def _load(self, html: str, base_url: str) -> None:
        if _TKINTERWEB_AVAILABLE:
            try:
                self._renderer.load_html(html, base_url=base_url)
            except TypeError:
                self._renderer.load_html(html)
        else:
            import re
            self._renderer.config(state=tk.NORMAL)
            self._renderer.delete("1.0", tk.END)
            self._renderer.insert(tk.END, re.sub(r"<[^>]+>", "", html))
            self._renderer.config(state=tk.DISABLED)

    def _render_welcome(self) -> None:
        self._load(_WELCOME_HTML, "")
