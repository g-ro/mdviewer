#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Markdown → HTML converter.

Improvements over the original
-------------------------------
* CSS is loaded from ``src/resources/github.css`` (externalised).
  A minimal inline fallback is used if the file cannot be read.
* The ``markdown.Markdown`` instance is cached and reset between calls
  instead of being reconstructed on every conversion.
* The ``UnicodeDecodeError`` latin-1 fallback is now logged as a warning.
"""
from __future__ import annotations

import markdown
from pathlib import Path

from config import cfg
from utils.logging_config import logger

# ---------------------------------------------------------------------------
# CSS loading — cached at first use
# ---------------------------------------------------------------------------
_FALLBACK_CSS = "body { font-family: sans-serif; padding: 20px; line-height: 1.6; }"
_css_cache: str | None = None


def _get_css() -> str:
    global _css_cache
    if _css_cache is None:
        _css_cache = _load_css()
    return _css_cache


def _load_css() -> str:
    try:
        return cfg.theme_css_path.read_text(encoding="utf-8")
    except OSError:
        logger.warning(
            "Could not read theme CSS from %s — using inline fallback",
            cfg.theme_css_path,
        )
        return _FALLBACK_CSS


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------
_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
{css}
</style>
</head>
<body>
{body}
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Markdown instance — cached and reset between calls (avoids re-loading
# all extensions on every conversion, which is the expensive part)
# ---------------------------------------------------------------------------
_md_instance: markdown.Markdown | None = None


def _get_md() -> markdown.Markdown:
    global _md_instance
    if _md_instance is None:
        _md_instance = markdown.Markdown(extensions=cfg.md_extensions)
    else:
        _md_instance.reset()
    return _md_instance


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def convert_md_to_html(file_path: str | Path) -> str:
    """Convert a Markdown file to a complete HTML document string."""
    path = Path(file_path)
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        logger.warning(
            "File %s is not valid UTF-8; retrying with latin-1", path
        )
        content = path.read_text(encoding="latin-1")

    body = _get_md().convert(content)
    return _HTML_TEMPLATE.format(css=_get_css(), body=body)


def convert_md_string_to_html(md_content: str) -> str:
    """Convert a Markdown string to a complete HTML document string."""
    body = _get_md().convert(md_content)
    return _HTML_TEMPLATE.format(css=_get_css(), body=body)
