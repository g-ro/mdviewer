#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Search / Find toolbar dialog.

``SearchBar`` is a small, modeless ``tk.Toplevel`` that provides the
find-in-document UI.  It is intentionally dumb:

  * It owns its widgets and layout.
  * It owns no search state and knows nothing about documents.
  * Every user action is forwarded to injected callbacks.
  * The owning ``DocumentViewer`` drives all logic.

Usage::

    bar = SearchBar(
        parent_window,
        on_search=viewer._on_search,
        on_next=viewer._on_search_next,
        on_previous=viewer._on_search_previous,
        on_close=viewer._on_search_close,
    )
    bar.focus_entry()

The dialog positions itself in the top-right corner of *parent_window* and
stays in front of it without blocking interaction (modeless / non-modal).
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from collections.abc import Callable


class SearchBar(tk.Toplevel):
    """
    Modeless find dialog anchored to the top-right of the parent window.

    Public methods
    --------------
    ``focus_entry()``             — focus the text entry (call on re-open)
    ``set_status(text, color)``   — update the match-count / message label
    ``get_term()``                — current text in the entry
    ``is_case_sensitive()``       — state of the "Match case" checkbox
    """

    _WIDTH  = 420
    _HEIGHT = 72

    def __init__(
        self,
        parent: tk.Tk | tk.Toplevel,
        on_search:   Callable[[str, bool], None],
        on_next:     Callable[[], None],
        on_previous: Callable[[], None],
        on_close:    Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._on_search   = on_search
        self._on_next     = on_next
        self._on_previous = on_previous
        self._on_close    = on_close

        self._term_var       = tk.StringVar()
        self._case_var       = tk.BooleanVar(value=False)
        self._last_term      = ""   # term used in last search
        self._last_case      = False

        self._build_ui()
        self._position(parent)

        # Modeless: transient keeps it above parent; no grab
        self.transient(parent)
        self.resizable(False, False)
        self.title("")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def focus_entry(self) -> None:
        """Move focus to the search entry and select its text."""
        self._entry.focus_set()
        self._entry.select_range(0, tk.END)

    def set_status(self, text: str, color: str = "#555555") -> None:
        """Update the status label (match count or message)."""
        self._status_lbl.configure(text=text, foreground=color)

    def get_term(self) -> str:
        return self._term_var.get()

    def is_case_sensitive(self) -> bool:
        return self._case_var.get()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.configure(bg="#f0f0f0", relief=tk.FLAT, bd=1)

        outer = ttk.Frame(self, padding=(6, 4, 6, 4))
        outer.pack(fill=tk.BOTH, expand=True)

        # ── Row 1: label + entry + buttons ───────────────────────────
        row1 = ttk.Frame(outer)
        row1.pack(fill=tk.X)

        ttk.Label(row1, text="🔍", font=("", 11)).pack(side=tk.LEFT, padx=(0, 4))

        self._entry = ttk.Entry(row1, textvariable=self._term_var, width=22)
        self._entry.pack(side=tk.LEFT, padx=(0, 4))

        ttk.Button(row1, text="Search",  width=7,
                   command=self._trigger_search).pack(side=tk.LEFT, padx=(0, 2))

        ttk.Button(row1, text="◀",  width=3,
                   command=self._on_previous).pack(side=tk.LEFT, padx=(0, 2))

        ttk.Button(row1, text="▶",  width=3,
                   command=self._on_next).pack(side=tk.LEFT, padx=(0, 6))

        ttk.Button(row1, text="✕",  width=3,
                   command=self._on_close).pack(side=tk.RIGHT)

        # ── Row 2: case checkbox + status ─────────────────────────────
        row2 = ttk.Frame(outer)
        row2.pack(fill=tk.X, pady=(3, 0))

        ttk.Checkbutton(
            row2, text="Match case",
            variable=self._case_var,
        ).pack(side=tk.LEFT)

        self._status_lbl = ttk.Label(row2, text="", foreground="#555555")
        self._status_lbl.pack(side=tk.RIGHT)

        # ── Keyboard bindings ─────────────────────────────────────────
        self._entry.bind("<Return>",    lambda _e: self._trigger_search())
        self._entry.bind("<KP_Enter>",  lambda _e: self._trigger_search())
        self.bind("<Escape>",           lambda _e: self._on_close())
        # Ctrl+G / F3 for Next; Shift+Ctrl+G / Shift+F3 for Previous
        self.bind("<F3>",               lambda _e: self._on_next())
        self.bind("<Shift-F3>",         lambda _e: self._on_previous())
        self.bind("<Control-g>",        lambda _e: self._on_next())
        self.bind("<Control-G>",        lambda _e: self._on_previous())

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------
    def _trigger_search(self) -> None:
        term = self._term_var.get().strip()
        if not term:
            self.set_status("Enter a search term", "#888888")
            return
        self._last_term = term
        self._last_case = self._case_var.get()
        self._on_search(term, self._last_case)

    def _position(self, parent: tk.Tk | tk.Toplevel) -> None:
        """Place the dialog at the top-right corner of *parent*."""
        parent.update_idletasks()
        px = parent.winfo_x()
        py = parent.winfo_y()
        pw = parent.winfo_width()
        x  = px + pw - self._WIDTH - 20
        y  = py + 60   # below menu bar + toolbar
        self.geometry(f"{self._WIDTH}x{self._HEIGHT}+{x}+{y}")
