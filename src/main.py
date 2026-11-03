#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MDViewer — entry point."""
import os
import sys

# Ensure src/ is importable when run directly as `python src/main.py`
_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import tkinter as tk
from tkinter import ttk

from views.main_window import MainWindow
from utils.logging_config import logger, install_global_exception_hooks


def main() -> None:
    root = tk.Tk()
    root.withdraw()

    install_global_exception_hooks(root)

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    MainWindow(root)

    root.eval("tk::PlaceWindow . center")
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
