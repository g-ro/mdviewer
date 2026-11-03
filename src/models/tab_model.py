#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pure-Python tab state model — no tkinter dependency.

Separates the overflow/promote/demote bookkeeping from UI code,
making the entire tab lifecycle fully unit-testable.

Two-tier tab list
-----------------
VISIBLE  — OrderedDict[tab_id, TabData]   (oldest first → front is demote candidate)
OVERFLOW — OrderedDict[tab_id, file_path] (oldest first → most-recently-parked is last)

All mutation methods return just enough information (demoted_id, promote_id) for
the UI layer to synchronise its widgets without reaching back into the model.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass


@dataclass
class TabData:
    """Rendered state of a single visible tab."""
    tab_id:    str
    file_path: str
    html:      str
    base_url:  str


class TabModel:
    """
    Manages the two-tier (visible + overflow) tab list.

    Rules
    -----
    * ``max_visible`` caps the rendered tier; 0 means no cap.
    * Adding a new visible tab when at capacity automatically demotes
      the oldest visible tab to overflow (HTML discarded, path kept).
    * Promoting an overflow tab re-uses the same ``tab_id`` so the
      path-to-id mapping never changes.
    """

    def __init__(self, max_visible: int = 5) -> None:
        self.max_visible                          = max_visible
        self._vis:      OrderedDict[str, TabData] = OrderedDict()
        self._ovf:      OrderedDict[str, str]     = OrderedDict()  # tab_id → path
        self._path_tab: dict[str, str]             = {}            # path → tab_id

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    @property
    def visible_count(self) -> int:
        return len(self._vis)

    @property
    def overflow_count(self) -> int:
        return len(self._ovf)

    @property
    def overflow_items(self) -> list[tuple[str, str]]:
        """[(tab_id, file_path)] most-recently-parked first."""
        return list(reversed(self._ovf.items()))

    def is_open(self, file_path: str) -> bool:
        return file_path in self._path_tab

    def is_visible(self, tab_id: str) -> bool:
        return tab_id in self._vis

    def tab_id_for(self, file_path: str) -> str | None:
        return self._path_tab.get(file_path)

    def get_visible(self, tab_id: str) -> TabData | None:
        return self._vis.get(tab_id)

    def get_overflow_path(self, tab_id: str) -> str | None:
        return self._ovf.get(tab_id)

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------
    def add_visible(self, data: TabData) -> str | None:
        """
        Add *data* to the visible tier.

        If the cap is reached, the oldest visible tab is demoted first.

        Returns:
            The ``tab_id`` that was demoted, or ``None``.
        """
        demoted_id: str | None = None
        if self.max_visible > 0 and len(self._vis) >= self.max_visible:
            demoted_id = self._demote_oldest()
        self._vis[data.tab_id]       = data
        self._path_tab[data.file_path] = data.tab_id
        return demoted_id

    def promote(self, tab_id: str, html: str, base_url: str) -> str | None:
        """
        Promote an overflow tab to visible, filling it with *html* / *base_url*.

        Returns:
            The ``tab_id`` that was demoted to make room, or ``None``.
        """
        if tab_id not in self._ovf:
            raise KeyError(f"tab_id {tab_id!r} is not in overflow")
        file_path = self._ovf.pop(tab_id)
        data = TabData(tab_id=tab_id, file_path=file_path,
                       html=html, base_url=base_url)
        return self.add_visible(data)

    def close_visible(self, tab_id: str) -> str | None:
        """
        Remove a visible tab entirely (both data and path registry).

        Returns:
            The most-recently-parked overflow ``tab_id`` to auto-promote,
            or ``None`` if overflow is empty.
        """
        data = self._vis.pop(tab_id, None)
        if data:
            self._path_tab.pop(data.file_path, None)
        return next(reversed(self._ovf), None) if self._ovf else None

    def close_overflow(self, tab_id: str) -> None:
        """Permanently remove a parked tab."""
        file_path = self._ovf.pop(tab_id, None)
        if file_path:
            self._path_tab.pop(file_path, None)

    def close_all_overflow(self) -> None:
        for fp in list(self._ovf.values()):
            self._path_tab.pop(fp, None)
        self._ovf.clear()

    def update_visible_html(self, tab_id: str, html: str, base_url: str) -> None:
        """Replace stored html/base_url for a visible tab (used on refresh)."""
        if tab_id in self._vis:
            self._vis[tab_id].html     = html
            self._vis[tab_id].base_url = base_url

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------
    def _demote_oldest(self) -> str:
        oldest_id, data = next(iter(self._vis.items()))
        del self._vis[oldest_id]
        self._ovf[oldest_id] = data.file_path
        # _path_tab entry intentionally kept: path still maps to this tab_id
        return oldest_id
