#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Markdown → HTML converter.

Public API
----------
``convert_md_to_html(file_path)``    — used internally for tab rendering
``convert_md_string_to_html(text)``  — utility for arbitrary strings
``export_as_html(source, output)``   — user-facing export to a standalone HTML file
"""
from __future__ import annotations

import html as html_module
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


def export_as_html(source_path: str | Path, output_path: str | Path) -> None:
    """
    Convert *source_path* from Markdown to a standalone HTML file at *output_path*.

    Differences from the internal ``convert_md_to_html`` render:

    * A ``<title>`` tag is injected using the source file's stem.
    * Every relative ``src`` / ``href`` attribute is rewritten to an
      absolute ``file://`` URL anchored at the source file's directory,
      so images and links resolve correctly when the HTML is opened in a
      browser from any location on the same machine.
    * The output directory is created automatically if it does not exist.

    Raises ``OSError`` on write failure.  Source-read errors (``OSError``,
    ``UnicodeDecodeError``) propagate to the caller for display in the UI.
    """
    # Deferred import — avoids a circular dependency at module load time
    # (temp_store → renderer; md_converter is imported by renderer indirectly)
    from utils.temp_store import _make_urls_absolute

    source = Path(source_path)
    output = Path(output_path)
    base_url = source.parent.as_uri() + "/"

    # Fresh render from disk — always reflects the saved file, not any cache
    html = convert_md_to_html(source)

    # Inject <title> from the source filename (HTML-escaped)
    title_tag = f"<title>{html_module.escape(source.stem)}</title>"
    html = html.replace("<head>", f"<head>\n{title_tag}", 1)

    # Rewrite relative src/href to absolute file:// URLs
    html = _make_urls_absolute(html, base_url)

    # Create output directory if it does not already exist
    output.parent.mkdir(parents=True, exist_ok=True)

    output.write_text(html, encoding="utf-8")
    logger.info("Exported %s → %s", source, output)
