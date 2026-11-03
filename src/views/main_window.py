#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Main application window for MDViewer."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser
from pathlib import Path

from views.file_explorer import FileExplorer
from views.document_viewer import DocumentViewer
from utils.logging_config import logger
from version import (
    __title__, __description__, __version__,
    __author__, __license__, __copyright__, __website__,
)


class MainWindow:
    """
    Root application window.

    Responsibilities:
    - Layout (PanedWindow → FileExplorer | DocumentViewer)
    - Menu + keyboard shortcuts
    - Status bar
    - Application lifecycle (startup, quit)
    """

    def __init__(self, root: tk.Tk) -> None:
        logger.info("Initializing MDViewer")
        self.root = root
        self.root.title(f"{__title__} v{__version__}")
        self.root.minsize(900, 600)
        self.root.geometry("1280x800")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main_frame = ttk.Frame(self.root, padding=4)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # Status bar must be created before DocumentViewer so the lambda
        # referencing _status_var is safe at first call
        self._status_var = tk.StringVar(value="Ready")

        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.grid(row=0, column=0, sticky="nsew")

        self.explorer = FileExplorer(paned, on_file_open=self._open_file)
        paned.add(self.explorer, weight=1)

        # Callback injected at construction — no post-hoc attribute assignment
        self.viewer = DocumentViewer(
            paned,
            on_status_update=lambda msg: self._status_var.set(msg),
        )
        paned.add(self.viewer, weight=4)

        ttk.Label(
            main_frame, textvariable=self._status_var,
            relief=tk.SUNKEN, anchor=tk.W,
        ).grid(row=1, column=0, sticky="ew", pady=(4, 0))

        self._create_menu()
        self._bind_shortcuts()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        logger.info("MDViewer ready")

    # ------------------------------------------------------------------
    def _create_menu(self) -> None:
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open File…      Ctrl+O", command=self._open_file_dialog)
        file_menu.add_command(label="Open Folder…",          command=self._open_folder_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Close Tab        Ctrl+W", command=self.viewer.close_current_tab)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)

        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Refresh          Ctrl+R", command=self.viewer.refresh_current_tab)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About",         command=self._show_about)
        help_menu.add_command(label="Visit Website", command=lambda: webbrowser.open(__website__))

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-o>", lambda _e: self._open_file_dialog())
        self.root.bind("<Control-w>", lambda _e: self.viewer.close_current_tab())
        self.root.bind("<Control-r>", lambda _e: self.viewer.refresh_current_tab())

    # ------------------------------------------------------------------
    def _open_file(self, file_path: str) -> None:
        logger.info("Opening: %s", file_path)
        self._status_var.set(f"Opened: {Path(file_path).name}")
        self.viewer.open_file(file_path)

    def _open_file_dialog(self) -> None:
        path = filedialog.askopenfilename(
            title="Open Markdown File",
            filetypes=[("Markdown files", "*.md *.markdown"), ("All files", "*.*")],
        )
        if path:
            self._open_file(path)

    def _open_folder_dialog(self) -> None:
        path = filedialog.askdirectory(title="Open Folder in Explorer")
        if path:
            self.explorer.set_root(path)
            self._status_var.set(f"Browsing: {path}")

    # ------------------------------------------------------------------
    def _show_about(self) -> None:
        """Display application information in a modal dialog."""
        win = tk.Toplevel(self.root)
        win.title(f"About {__title__}")
        win.geometry("420x300")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        win.geometry(f"+{self.root.winfo_x() + 160}+{self.root.winfo_y() + 120}")

        f = ttk.Frame(win, padding=24)
        f.pack(fill=tk.BOTH, expand=True)

        ttk.Label(f, text=f"{__title__} v{__version__}",
                  font=("Helvetica", 16, "bold")).pack(pady=(0, 8))
        ttk.Label(f, text=__description__, wraplength=360, justify=tk.CENTER).pack()
        ttk.Label(f, text=f"\nDeveloper: {__author__}").pack()
        ttk.Label(f, text=f"{__copyright__}  •  {__license__}",
                  justify=tk.CENTER).pack(pady=(12, 0))

        link = ttk.Label(f, text=__website__, foreground="blue", cursor="hand2")
        link.pack(pady=(8, 16))
        link.bind("<Button-1>", lambda _e: webbrowser.open(__website__))

        ttk.Button(f, text="Close", command=win.destroy).pack()

    def _on_close(self) -> None:
        if messagebox.askokcancel("Quit", "Do you want to quit MDViewer?"):
            logger.info("Shutting down")
            self.root.destroy()
