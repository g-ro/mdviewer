#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build Script for MDViewer
~~~~~~~~~~~~~~~~~~~~~~~~~

Creates a single-file Windows executable using PyInstaller.

Usage:
    uv run --group build python build_exe.py

Output:  dist/MDViewer.exe
"""
import os
import sys

import PyInstaller.__main__


def build_exe() -> None:
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(script_dir, "src", "main.py")
    src_dir     = os.path.join(script_dir, "src")

    # Optional icon — skip silently if not present
    icon_path = os.path.join(script_dir, "resources", "mdviewer.ico")
    icon_args = [f"--icon={icon_path}"] if os.path.exists(icon_path) else []

    args = [
        main_script,
        "--name=MDViewer",
        "--onefile",
        "--windowed",   # no console window
        "--clean",
        "--noconfirm",

        # ── Key fix ────────────────────────────────────────────────────
        # Tell PyInstaller where the app's own modules live so it can
        # collect views.*, utils.*, and version during static analysis.
        f"--paths={src_dir}",

        # ── App modules (hidden-import as belt-and-suspenders) ─────────
        "--hidden-import=version",
        "--hidden-import=views",
        "--hidden-import=views.main_window",
        "--hidden-import=views.file_explorer",
        "--hidden-import=views.document_viewer",
        "--hidden-import=utils",
        "--hidden-import=utils.logging_config",
        "--hidden-import=utils.md_converter",

        # ── tkinter ────────────────────────────────────────────────────
        "--hidden-import=tkinter",
        "--hidden-import=tkinter.ttk",
        "--hidden-import=tkinter.scrolledtext",

        # ── markdown + extensions ──────────────────────────────────────
        "--hidden-import=markdown",
        "--hidden-import=markdown.extensions.tables",
        "--hidden-import=markdown.extensions.fenced_code",
        "--hidden-import=markdown.extensions.toc",
        "--hidden-import=markdown.extensions.nl2br",
        "--hidden-import=markdown.extensions.attr_list",
        "--hidden-import=markdown.extensions.def_list",
        "--hidden-import=markdown.extensions.footnotes",
        "--collect-all=markdown",

        # ── tkinterweb (bundles its Tcl/Tk html widget) ────────────────
        "--collect-all=tkinterweb",
        "--collect-all=tkinterweb_tkhtml",

        *icon_args,
    ]

    print(f"Entry point : {main_script}")
    print(f"Module path : {src_dir}")
    print(f"Output dir  : {os.path.join(script_dir, 'dist')}")
    print()
    PyInstaller.__main__.run(args)


if __name__ == "__main__":
    build_exe()
