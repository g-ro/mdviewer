"""
Tests for utils.md_converter.

Coverage areas
--------------
* UTF-8 file conversion
* Latin-1 fallback (file not valid UTF-8)
* HTML document structure (DOCTYPE, head, body, style)
* Markdown features: headers, tables, fenced code, links
* CSS is included in output
* convert_md_string_to_html helper
* Missing file raises FileNotFoundError
* Repeated calls use the cached Markdown instance (no state bleed between calls)
"""
from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def utf8_md(tmp_path: Path) -> Path:
    p = tmp_path / "sample.md"
    p.write_text(
        "# Hello World\n\nSome **bold** and _italic_ text.\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def latin1_md(tmp_path: Path) -> Path:
    """File with a byte that is invalid UTF-8 but valid latin-1 (é = 0xe9)."""
    p = tmp_path / "latin1.md"
    p.write_bytes(b"# Caf\xe9\n\nA file with a latin-1 byte.\n")
    return p


@pytest.fixture
def table_md(tmp_path: Path) -> Path:
    p = tmp_path / "table.md"
    p.write_text(
        "| Col A | Col B |\n|---|---|\n| 1 | 2 |\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def fenced_md(tmp_path: Path) -> Path:
    p = tmp_path / "code.md"
    p.write_text(
        "```python\nprint('hello')\n```\n",
        encoding="utf-8",
    )
    return p


# ---------------------------------------------------------------------------
# HTML structure
# ---------------------------------------------------------------------------
class TestHtmlStructure:
    def test_doctype(self, utf8_md):
        from utils.md_converter import convert_md_to_html
        html = convert_md_to_html(utf8_md)
        assert html.strip().startswith("<!DOCTYPE html>")

    def test_has_head_and_body(self, utf8_md):
        from utils.md_converter import convert_md_to_html
        html = convert_md_to_html(utf8_md)
        assert "<head>" in html
        assert "</head>" in html
        assert "<body>" in html
        assert "</body>" in html

    def test_css_embedded(self, utf8_md):
        from utils.md_converter import convert_md_to_html
        html = convert_md_to_html(utf8_md)
        assert "<style>" in html
        # Should have at least some CSS rules
        assert "font-family" in html

    def test_charset_meta(self, utf8_md):
        from utils.md_converter import convert_md_to_html
        html = convert_md_to_html(utf8_md)
        assert 'charset="UTF-8"' in html


# ---------------------------------------------------------------------------
# UTF-8 content
# ---------------------------------------------------------------------------
class TestUtf8Conversion:
    def test_h1_rendered(self, utf8_md):
        from utils.md_converter import convert_md_to_html
        html = convert_md_to_html(utf8_md)
        assert "<h1" in html          # toc extension adds id="..." attribute
        assert "Hello World" in html

    def test_bold_rendered(self, utf8_md):
        from utils.md_converter import convert_md_to_html
        html = convert_md_to_html(utf8_md)
        assert "<strong>bold</strong>" in html

    def test_italic_rendered(self, utf8_md):
        from utils.md_converter import convert_md_to_html
        html = convert_md_to_html(utf8_md)
        assert "<em>italic</em>" in html

    def test_accepts_path_object(self, utf8_md):
        from utils.md_converter import convert_md_to_html
        html = convert_md_to_html(utf8_md)          # Path object
        html2 = convert_md_to_html(str(utf8_md))    # str
        assert html == html2


# ---------------------------------------------------------------------------
# Latin-1 fallback
# ---------------------------------------------------------------------------
class TestLatin1Fallback:
    def test_does_not_raise(self, latin1_md):
        from utils.md_converter import convert_md_to_html
        html = convert_md_to_html(latin1_md)
        assert "<h1" in html          # toc extension adds id="..." attribute

    def test_content_decoded(self, latin1_md):
        from utils.md_converter import convert_md_to_html
        html = convert_md_to_html(latin1_md)
        # é decoded from latin-1 → should appear in output
        assert "Caf" in html


# ---------------------------------------------------------------------------
# Markdown extensions
# ---------------------------------------------------------------------------
class TestExtensions:
    def test_table_rendered(self, table_md):
        from utils.md_converter import convert_md_to_html
        html = convert_md_to_html(table_md)
        assert "<table>" in html
        assert "<th>" in html
        assert "Col A" in html

    def test_fenced_code_rendered(self, fenced_md):
        from utils.md_converter import convert_md_to_html
        html = convert_md_to_html(fenced_md)
        assert "<code" in html
        assert "print" in html


# ---------------------------------------------------------------------------
# convert_md_string_to_html
# ---------------------------------------------------------------------------
class TestConvertString:
    def test_basic_conversion(self):
        from utils.md_converter import convert_md_string_to_html
        html = convert_md_string_to_html("# Title\n\nParagraph.")
        assert "<h1" in html          # toc extension adds id="..." attribute
        assert "Title" in html
        assert "<p>" in html

    def test_returns_complete_document(self):
        from utils.md_converter import convert_md_string_to_html
        html = convert_md_string_to_html("hello")
        assert "<!DOCTYPE html>" in html
        assert "<body>" in html

    def test_empty_string(self):
        from utils.md_converter import convert_md_string_to_html
        html = convert_md_string_to_html("")
        assert "<!DOCTYPE html>" in html  # structure still intact


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------
class TestErrorCases:
    def test_missing_file_raises(self, tmp_path):
        from utils.md_converter import convert_md_to_html
        with pytest.raises((FileNotFoundError, OSError)):
            convert_md_to_html(tmp_path / "does_not_exist.md")


# ---------------------------------------------------------------------------
# State isolation between calls (cached Markdown instance must reset)
# ---------------------------------------------------------------------------
class TestCachedInstanceReset:
    def test_toc_does_not_bleed_between_calls(self, tmp_path):
        """
        The [TOC] extension accumulates headings internally.
        After a reset(), a second call must not include headings from the first.
        """
        from utils.md_converter import convert_md_string_to_html

        html1 = convert_md_string_to_html("# Doc One\n## Section A\n")
        html2 = convert_md_string_to_html("# Doc Two\n## Section B\n")

        assert "Doc One"   in html1
        assert "Doc One"   not in html2
        assert "Section B" in html2
        assert "Section B" not in html1

    def test_repeated_calls_consistent(self, utf8_md):
        from utils.md_converter import convert_md_to_html
        html_a = convert_md_to_html(utf8_md)
        html_b = convert_md_to_html(utf8_md)
        assert html_a == html_b
