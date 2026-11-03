#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MDViewer — development entry point.
Run with: uv run python main.py
"""
import importlib.util
import os
import sys

if __name__ == "__main__":
    src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
    sys.path.insert(0, src_dir)

    spec = importlib.util.spec_from_file_location(
        "mdviewer_main", os.path.join(src_dir, "main.py")
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    mod.main()
