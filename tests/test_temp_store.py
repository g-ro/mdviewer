"""
Tests for utils.temp_store.TempHtmlStore.

All tests use a fresh store pointed at a pytest tmp_path so they never
touch the real %TEMP%/mdviewer directory.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from utils.temp_store import TempHtmlStore, _make_urls_absolute


# ---------------------------------------------------------------------------
# Fixture: isolated store per test
# ---------------------------------------------------------------------------
@pytest.fixture
def store(tmp_path: Path) -> TempHtmlStore:
    """A TempHtmlStore whose directory is isolated inside tmp_path."""
    s = TempHtmlStore.__new__(TempHtmlStore)      # bypass __init__ side effects
    s._dir = tmp_path / "mdviewer_test"
    s._dir.mkdir()
    return s


# ---------------------------------------------------------------------------
# write / uri_for / release
# ---------------------------------------------------------------------------
class TestWriteAndRelease:
    def test_write_creates_file(self, store):
        store.write("tab1", "<h1>Hello</h1>")
        assert (store._dir / "tab1.html").exists()

    def test_write_returns_path(self, store):
        p = store.write("tab1", "<p>test</p>")
        assert p == store._dir / "tab1.html"

    def test_write_content_correct(self, store):
        store.write("tab1", "<h1>Hello</h1>")
        content = (store._dir / "tab1.html").read_text(encoding="utf-8")
        assert "<h1>Hello</h1>" in content

    def test_write_overwrites_existing(self, store):
        store.write("tab1", "<p>first</p>")
        store.write("tab1", "<p>second</p>")
        content = (store._dir / "tab1.html").read_text(encoding="utf-8")
        assert "second" in content
        assert "first" not in content

    def test_uri_for_returns_file_uri(self, store):
        uri = store.uri_for("tab1")
        assert uri.startswith("file://")
        assert "tab1.html" in uri

    def test_release_deletes_file(self, store):
        store.write("tab1", "<p>x</p>")
        store.release("tab1")
        assert not (store._dir / "tab1.html").exists()

    def test_release_nonexistent_is_safe(self, store):
        store.release("ghost")  # must not raise

    def test_multiple_keys_are_independent(self, store):
        store.write("tab1", "<p>one</p>")
        store.write("tab2", "<p>two</p>")
        store.release("tab1")
        assert not (store._dir / "tab1.html").exists()
        assert (store._dir / "tab2.html").exists()


# ---------------------------------------------------------------------------
# cleanup_all
# ---------------------------------------------------------------------------
class TestCleanupAll:
    def test_removes_all_html_files(self, store):
        store.write("a", "<p>a</p>")
        store.write("b", "<p>b</p>")
        store.cleanup_all()
        assert list(store._dir.glob("*.html")) == []

    def test_cleanup_empty_dir_is_safe(self, store):
        store.cleanup_all()  # must not raise

    def test_does_not_remove_non_html_files(self, store):
        (store._dir / "keep.txt").write_text("hi")
        store.write("tab1", "<p>x</p>")
        store.cleanup_all()
        assert (store._dir / "keep.txt").exists()


# ---------------------------------------------------------------------------
# URL pre-processing
# ---------------------------------------------------------------------------
class TestMakeUrlsAbsolute:
    BASE = "file:///C:/docs/project/"

    def test_relative_image_src_made_absolute(self):
        html = '<img src="diagram.png">'
        result = _make_urls_absolute(html, self.BASE)
        assert 'src="file:///C:/docs/project/diagram.png"' in result

    def test_relative_href_made_absolute(self):
        html = '<a href="other.md">link</a>'
        result = _make_urls_absolute(html, self.BASE)
        assert 'href="file:///C:/docs/project/other.md"' in result

    def test_anchor_unchanged(self):
        html = '<a href="#section">go</a>'
        result = _make_urls_absolute(html, self.BASE)
        assert 'href="#section"' in result

    def test_external_https_unchanged(self):
        html = '<a href="https://example.com">ext</a>'
        result = _make_urls_absolute(html, self.BASE)
        assert 'href="https://example.com"' in result

    def test_already_absolute_file_url_unchanged(self):
        html = '<img src="file:///C:/abs/img.png">'
        result = _make_urls_absolute(html, self.BASE)
        assert 'src="file:///C:/abs/img.png"' in result

    def test_data_uri_unchanged(self):
        html = '<img src="data:image/png;base64,abc==">'
        result = _make_urls_absolute(html, self.BASE)
        assert 'src="data:image/png;base64,abc=="' in result

    def test_single_quote_attributes_handled(self):
        html = "<img src='image.png'>"
        result = _make_urls_absolute(html, self.BASE)
        assert "file:///C:/docs/project/image.png" in result

    def test_write_applies_base_url_preprocessing(self, store):
        html = '<img src="img.png">'
        store.write("t1", html, base_url=self.BASE)
        written = (store._dir / "t1.html").read_text(encoding="utf-8")
        assert "file:///C:/docs/project/img.png" in written

    def test_write_without_base_url_unchanged(self, store):
        html = '<img src="img.png">'
        store.write("t1", html)
        written = (store._dir / "t1.html").read_text(encoding="utf-8")
        assert 'src="img.png"' in written
