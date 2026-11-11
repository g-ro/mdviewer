"""
Tests for the _SearchState navigation model.

_SearchState is pure Python with no tkinter dependency so it is fully
unit-testable.  We import it directly from document_viewer.
"""
from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from views.document_viewer import _SearchState


def _state(count: int, current: int = 1) -> _SearchState:
    return _SearchState(
        term="test",
        ignore_case=True,
        match_count=count,
        current=current,
    )


# ---------------------------------------------------------------------------
# advance (Next)
# ---------------------------------------------------------------------------
class TestAdvance:
    def test_moves_forward(self):
        s = _state(5, current=1)
        s.advance()
        assert s.current == 2

    def test_moves_through_all_matches(self):
        s = _state(3, current=1)
        s.advance()
        assert s.current == 2
        s.advance()
        assert s.current == 3

    def test_wraps_last_to_first(self):
        s = _state(5, current=5)
        wrapped = s.advance()
        assert wrapped is True
        assert s.current == 1

    def test_no_wrap_when_not_at_end(self):
        s = _state(5, current=3)
        wrapped = s.advance()
        assert wrapped is False
        assert s.current == 4

    def test_zero_matches_returns_false(self):
        s = _state(0, current=0)
        wrapped = s.advance()
        assert wrapped is False
        assert s.current == 0

    def test_single_match_wraps(self):
        s = _state(1, current=1)
        wrapped = s.advance()
        assert wrapped is True
        assert s.current == 1

    def test_two_matches_cycle(self):
        s = _state(2, current=1)
        s.advance()
        assert s.current == 2
        s.advance()
        assert s.current == 1


# ---------------------------------------------------------------------------
# retreat (Previous)
# ---------------------------------------------------------------------------
class TestRetreat:
    def test_moves_backward(self):
        s = _state(5, current=3)
        s.retreat()
        assert s.current == 2

    def test_wraps_first_to_last(self):
        s = _state(5, current=1)
        wrapped = s.retreat()
        assert wrapped is True
        assert s.current == 5

    def test_no_wrap_when_not_at_start(self):
        s = _state(5, current=3)
        wrapped = s.retreat()
        assert wrapped is False
        assert s.current == 2

    def test_zero_matches_returns_false(self):
        s = _state(0, current=0)
        wrapped = s.retreat()
        assert wrapped is False

    def test_single_match_wraps(self):
        s = _state(1, current=1)
        wrapped = s.retreat()
        assert wrapped is True
        assert s.current == 1

    def test_two_matches_cycle(self):
        s = _state(2, current=2)
        s.retreat()
        assert s.current == 1
        s.retreat()
        assert s.current == 2


# ---------------------------------------------------------------------------
# advance + retreat symmetry
# ---------------------------------------------------------------------------
class TestSymmetry:
    def test_advance_then_retreat_returns_to_start(self):
        s = _state(5, current=3)
        s.advance()   # → 4
        s.retreat()   # → 3
        assert s.current == 3

    def test_full_cycle_advance(self):
        s = _state(4, current=1)
        for _ in range(4):
            s.advance()
        assert s.current == 1   # back to start after full cycle

    def test_full_cycle_retreat(self):
        s = _state(4, current=1)
        for _ in range(4):
            s.retreat()
        assert s.current == 1


# ---------------------------------------------------------------------------
# status_text
# ---------------------------------------------------------------------------
class TestStatusText:
    def test_no_results(self):
        s = _state(0)
        assert "No results" in s.status_text

    def test_shows_current_and_total(self):
        s = _state(10, current=3)
        assert s.status_text == "3 of 10"

    def test_single_result(self):
        s = _state(1, current=1)
        assert s.status_text == "1 of 1"
