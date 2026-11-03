"""
pytest configuration and shared fixtures.

Adds src/ to sys.path so all test modules can import the application
packages (config, models, utils, views) without an installation step.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
SRC_DIR  = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

# ── Shared fixtures ───────────────────────────────────────────────────────────
import pytest


@pytest.fixture
def tmp_md_file(tmp_path: Path):
    """Factory fixture — returns a callable that creates a temp .md file."""
    def _make(content: str, filename: str = "doc.md", encoding: str = "utf-8") -> Path:
        p = tmp_path / filename
        p.write_bytes(content.encode(encoding))
        return p
    return _make
