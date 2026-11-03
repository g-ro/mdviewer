"""
Tests for models.tab_model — the pure-Python tab lifecycle model.

These tests run without any tkinter dependency.

Coverage areas
--------------
* Adding visible tabs (under cap, at cap, no-cap mode)
* Demotion of oldest visible tab when cap is reached
* Promotion from overflow to visible
* Close (visible + overflow + close-all)
* Auto-promote candidate after a close
* Querying state (is_open, is_visible, counts, overflow_items order)
* Edge cases (empty model, unknown tab_id, repeated open)
"""
from __future__ import annotations

import pytest

from models.tab_model import TabData, TabModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _data(n: int) -> TabData:
    """Create minimal TabData for tab number *n*."""
    return TabData(
        tab_id=f"t{n}",
        file_path=f"/docs/file{n}.md",
        html=f"<h1>File {n}</h1>",
        base_url=f"file:///docs/",
    )


# ---------------------------------------------------------------------------
# add_visible
# ---------------------------------------------------------------------------
class TestAddVisible:
    def test_below_cap_no_demotion(self):
        m = TabModel(max_visible=3)
        assert m.add_visible(_data(1)) is None
        assert m.add_visible(_data(2)) is None
        assert m.visible_count == 2
        assert m.overflow_count == 0

    def test_exactly_at_cap_no_demotion(self):
        m = TabModel(max_visible=3)
        m.add_visible(_data(1))
        m.add_visible(_data(2))
        assert m.add_visible(_data(3)) is None
        assert m.visible_count == 3

    def test_exceeds_cap_demotes_oldest(self):
        m = TabModel(max_visible=3)
        m.add_visible(_data(1))
        m.add_visible(_data(2))
        m.add_visible(_data(3))
        demoted = m.add_visible(_data(4))
        assert demoted == "t1"
        assert m.visible_count == 3
        assert m.overflow_count == 1

    def test_cap_zero_means_no_limit(self):
        m = TabModel(max_visible=0)
        for i in range(20):
            m.add_visible(_data(i))
        assert m.visible_count == 20
        assert m.overflow_count == 0

    def test_demoted_path_accessible_in_overflow(self):
        m = TabModel(max_visible=2)
        m.add_visible(_data(1))
        m.add_visible(_data(2))
        m.add_visible(_data(3))
        assert m.get_overflow_path("t1") == "/docs/file1.md"

    def test_path_still_tracked_after_demotion(self):
        """Demoted file is still in is_open — just in overflow, not visible."""
        m = TabModel(max_visible=2)
        m.add_visible(_data(1))
        m.add_visible(_data(2))
        m.add_visible(_data(3))
        assert m.is_open("/docs/file1.md")
        assert not m.is_visible("t1")

    def test_cap_one_always_demotes_previous(self):
        m = TabModel(max_visible=1)
        m.add_visible(_data(1))
        d2 = m.add_visible(_data(2))
        assert d2 == "t1"
        d3 = m.add_visible(_data(3))
        assert d3 == "t2"
        assert m.visible_count == 1
        assert m.overflow_count == 2


# ---------------------------------------------------------------------------
# is_open / is_visible / queries
# ---------------------------------------------------------------------------
class TestQueries:
    def test_is_open_visible_tab(self):
        m = TabModel(max_visible=5)
        m.add_visible(_data(1))
        assert m.is_open("/docs/file1.md")

    def test_is_open_overflow_tab(self):
        m = TabModel(max_visible=1)
        m.add_visible(_data(1))
        m.add_visible(_data(2))  # demotes t1
        assert m.is_open("/docs/file1.md")

    def test_is_open_unknown(self):
        m = TabModel(max_visible=5)
        assert not m.is_open("/no/such/file.md")

    def test_tab_id_for_returns_id(self):
        m = TabModel(max_visible=5)
        m.add_visible(_data(1))
        assert m.tab_id_for("/docs/file1.md") == "t1"

    def test_tab_id_for_unknown_returns_none(self):
        m = TabModel(max_visible=5)
        assert m.tab_id_for("/unknown.md") is None

    def test_get_visible_returns_data(self):
        m = TabModel(max_visible=5)
        m.add_visible(_data(1))
        d = m.get_visible("t1")
        assert d is not None
        assert d.file_path == "/docs/file1.md"

    def test_get_visible_unknown_returns_none(self):
        m = TabModel(max_visible=5)
        assert m.get_visible("nonexistent") is None

    def test_overflow_items_most_recent_first(self):
        """Most-recently demoted tab appears first in overflow_items."""
        m = TabModel(max_visible=1)
        m.add_visible(_data(1))
        m.add_visible(_data(2))  # demotes t1  → ovf: [t1]
        m.add_visible(_data(3))  # demotes t2  → ovf: [t1, t2]
        items = m.overflow_items  # reversed → [t2, t1]
        assert items[0][0] == "t2"
        assert items[1][0] == "t1"

    def test_counts(self):
        m = TabModel(max_visible=2)
        m.add_visible(_data(1))
        m.add_visible(_data(2))
        m.add_visible(_data(3))
        assert m.visible_count == 2
        assert m.overflow_count == 1


# ---------------------------------------------------------------------------
# promote
# ---------------------------------------------------------------------------
class TestPromote:
    def test_promote_makes_tab_visible(self):
        m = TabModel(max_visible=2)
        m.add_visible(_data(1))
        m.add_visible(_data(2))
        m.add_visible(_data(3))  # demotes t1
        m.promote("t1", html="<p>back</p>", base_url="file:///docs/")
        assert m.is_visible("t1")
        assert m.overflow_count == 1  # t2 was demoted

    def test_promote_updates_html(self):
        m = TabModel(max_visible=2)
        m.add_visible(_data(1))
        m.add_visible(_data(2))
        m.add_visible(_data(3))  # demotes t1
        m.promote("t1", html="<p>fresh</p>", base_url="x://")
        assert m.get_visible("t1").html == "<p>fresh</p>"

    def test_promote_causes_demotion_when_at_cap(self):
        m = TabModel(max_visible=2)
        m.add_visible(_data(1))
        m.add_visible(_data(2))
        m.add_visible(_data(3))  # demotes t1; visible=[t2,t3] ovf=[t1]
        demoted = m.promote("t1", html="", base_url="")
        # Promoting t1 when visible=[t2,t3] at cap → demotes t2
        assert demoted == "t2"
        assert m.is_visible("t1")
        assert m.get_overflow_path("t2") == "/docs/file2.md"

    def test_promote_no_demotion_when_below_cap(self):
        m = TabModel(max_visible=3)
        m.add_visible(_data(1))
        m.add_visible(_data(2))
        m.add_visible(_data(3))
        m.add_visible(_data(4))  # demotes t1; visible=[t2,t3,t4]
        m.close_visible("t4")    # visible=[t2,t3]
        demoted = m.promote("t1", html="", base_url="")
        assert demoted is None   # room available; no demotion
        assert m.visible_count == 3

    def test_promote_invalid_tab_id_raises(self):
        m = TabModel(max_visible=5)
        with pytest.raises(KeyError):
            m.promote("no-such-tab", html="", base_url="")

    def test_promote_removes_from_overflow(self):
        m = TabModel(max_visible=1)
        m.add_visible(_data(1))
        m.add_visible(_data(2))  # demotes t1
        m.promote("t1", html="", base_url="")
        assert m.get_overflow_path("t1") is None


# ---------------------------------------------------------------------------
# close_visible
# ---------------------------------------------------------------------------
class TestCloseVisible:
    def test_close_removes_path_from_registry(self):
        m = TabModel(max_visible=5)
        m.add_visible(_data(1))
        m.close_visible("t1")
        assert not m.is_open("/docs/file1.md")
        assert m.tab_id_for("/docs/file1.md") is None

    def test_close_with_no_overflow_returns_none(self):
        m = TabModel(max_visible=5)
        m.add_visible(_data(1))
        result = m.close_visible("t1")
        assert result is None

    def test_close_with_overflow_returns_most_recent_parked(self):
        m = TabModel(max_visible=1)
        m.add_visible(_data(1))
        m.add_visible(_data(2))  # demotes t1 → ovf=[t1]
        m.add_visible(_data(3))  # demotes t2 → ovf=[t1,t2]  visible=[t3]
        result = m.close_visible("t3")
        assert result == "t2"    # most recently parked

    def test_close_visible_decrements_count(self):
        m = TabModel(max_visible=5)
        m.add_visible(_data(1))
        m.add_visible(_data(2))
        m.close_visible("t1")
        assert m.visible_count == 1

    def test_close_unknown_tab_is_safe(self):
        m = TabModel(max_visible=5)
        result = m.close_visible("nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# close_overflow / close_all_overflow
# ---------------------------------------------------------------------------
class TestCloseOverflow:
    def test_close_overflow_removes_entry(self):
        m = TabModel(max_visible=1)
        m.add_visible(_data(1))
        m.add_visible(_data(2))  # demotes t1
        m.close_overflow("t1")
        assert m.overflow_count == 0
        assert not m.is_open("/docs/file1.md")

    def test_close_overflow_unknown_is_safe(self):
        m = TabModel(max_visible=5)
        m.close_overflow("ghost")  # should not raise

    def test_close_all_overflow_clears_all(self):
        m = TabModel(max_visible=1)
        m.add_visible(_data(1))
        m.add_visible(_data(2))  # ovf=[t1]
        m.add_visible(_data(3))  # ovf=[t1,t2]
        m.close_all_overflow()
        assert m.overflow_count == 0
        assert not m.is_open("/docs/file1.md")
        assert not m.is_open("/docs/file2.md")
        # Current visible tab unaffected
        assert m.is_open("/docs/file3.md")

    def test_close_all_overflow_empty_is_safe(self):
        m = TabModel(max_visible=5)
        m.close_all_overflow()


# ---------------------------------------------------------------------------
# update_visible_html
# ---------------------------------------------------------------------------
class TestUpdateVisibleHtml:
    def test_updates_stored_html(self):
        m = TabModel(max_visible=5)
        m.add_visible(_data(1))
        m.update_visible_html("t1", html="<p>updated</p>", base_url="x://")
        assert m.get_visible("t1").html == "<p>updated</p>"
        assert m.get_visible("t1").base_url == "x://"

    def test_update_unknown_tab_is_safe(self):
        m = TabModel(max_visible=5)
        m.update_visible_html("ghost", html="x", base_url="")
