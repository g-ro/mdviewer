#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""File explorer panel — shows a lazy directory tree filtered to .md files."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog
from collections.abc import Callable
from pathlib import Path

from utils.logging_config import logger

# Tree-view tag constants — single source of truth for tag names
_TAG_DIR         = "dir"
_TAG_MD          = "md"
_TAG_PLACEHOLDER = "placeholder"


class FileExplorer(ttk.Frame):
    """
    Left-panel directory tree.

    Double-clicking a .md file calls ``on_file_open(file_path)``.
    Directories expand lazily (children are loaded on first expand).
    Dot-directories are shown; dot-files are hidden.
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_file_open: Callable[[str], None],
    ) -> None:
        super().__init__(parent)
        self._on_file_open = on_file_open
        self._root_path: Path | None = None
        self._build_ui()
        self.set_root(Path.home())

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 2))

        self._path_var = tk.StringVar()
        path_entry = ttk.Entry(toolbar, textvariable=self._path_var)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        path_entry.bind("<Return>", self._on_path_enter)

        ttk.Button(toolbar, text="📂", width=3, command=self._browse).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="↺",  width=3, command=self._refresh).pack(
            side=tk.LEFT, padx=(2, 0)
        )

        # Tree + scrollbars
        tree_frame = ttk.Frame(self)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self._tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        self._tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",   command=self._tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self._tree.xview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Tag styling
        self._tree.tag_configure(_TAG_MD,  foreground="#0366d6")
        self._tree.tag_configure(_TAG_DIR, foreground="#24292e")

        # Events
        self._tree.bind("<<TreeviewOpen>>", self._on_expand)
        self._tree.bind("<Double-1>",       self._on_double_click)
        self._tree.bind("<Return>",         self._on_return_key)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------
    def set_root(self, path: str | Path) -> None:
        root = Path(path)
        if not root.is_dir():
            logger.warning("Not a directory: %s", root)
            return
        self._root_path = root
        self._path_var.set(str(root))
        self._populate_root()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------
    def _populate_root(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        if not self._root_path:
            return
        label = self._root_path.name or str(self._root_path)
        root_id = self._tree.insert(
            "", "end",
            text=f"📁 {label}",
            values=[str(self._root_path)],
            tags=[_TAG_DIR],
            open=True,
        )
        self._load_children(root_id, self._root_path)

    def _load_children(self, parent_id: str, path: Path) -> None:
        try:
            entries = sorted(
                path.iterdir(),
                key=lambda e: (not e.is_dir(), e.name.lower()),
            )
        except PermissionError:
            return

        for entry in entries:
            # Show dot-directories; hide dot-files
            if entry.name.startswith(".") and not entry.is_dir():
                continue
            if entry.is_dir():
                iid = self._tree.insert(
                    parent_id, "end",
                    text=f"📁 {entry.name}",
                    values=[str(entry)],
                    tags=[_TAG_DIR],
                )
                # Placeholder triggers the expand arrow and lazy loading
                self._tree.insert(iid, "end", text="…", tags=[_TAG_PLACEHOLDER])
            elif entry.suffix.lower() in (".md", ".markdown"):
                self._tree.insert(
                    parent_id, "end",
                    text=f"📝 {entry.name}",
                    values=[str(entry)],
                    tags=[_TAG_MD],
                )

    def _on_expand(self, _event) -> None:
        item_id = self._tree.focus()
        values  = self._tree.item(item_id, "values")
        if not values:
            return
        children = self._tree.get_children(item_id)
        if (
            len(children) == 1
            and _TAG_PLACEHOLDER in self._tree.item(children[0], "tags")
        ):
            self._tree.delete(children[0])
            self._load_children(item_id, Path(values[0]))

    def _on_double_click(self, event) -> None:
        item_id = self._tree.identify_row(event.y)
        if item_id and _TAG_MD in self._tree.item(item_id, "tags"):
            values = self._tree.item(item_id, "values")
            if values:
                self._on_file_open(values[0])

    def _on_return_key(self, _event) -> None:
        item_id = self._tree.focus()
        if item_id and _TAG_MD in self._tree.item(item_id, "tags"):
            values = self._tree.item(item_id, "values")
            if values:
                self._on_file_open(values[0])

    def _browse(self) -> None:
        path = filedialog.askdirectory(
            title="Select folder",
            initialdir=str(self._root_path or Path.home()),
        )
        if path:
            self.set_root(path)

    def _on_path_enter(self, _event) -> None:
        p = self._path_var.get().strip()
        if p:
            self.set_root(p)

    def _refresh(self) -> None:
        if self._root_path:
            self._populate_root()
