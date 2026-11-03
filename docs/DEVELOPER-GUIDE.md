# MDViewer — Developer Guide

**Version:** 1.0.0  
**Python:** 3.13+  
**Last updated:** 2026

---

## Table of Contents

1. [Overview](#1-overview)
2. [Technology Stack](#2-technology-stack)
3. [Project Structure](#3-project-structure)
4. [Architecture](#4-architecture)
5. [Module Reference](#5-module-reference)
6. [Key Design Patterns](#6-key-design-patterns)
7. [File-to-Screen: Full Call Stack](#7-file-to-screen-full-call-stack)
8. [Data Flow Walkthrough](#8-data-flow-walkthrough)
9. [The Tab Lifecycle](#9-the-tab-lifecycle)
10. [HTML Rendering: Problems and Solutions](#10-html-rendering-problems-and-solutions)
11. [Configuration Reference](#11-configuration-reference)
12. [Extending the Application](#12-extending-the-application)
13. [Testing](#13-testing)
14. [Building the Executable](#14-building-the-executable)
15. [Development Workflow](#15-development-workflow)
16. [Known Constraints](#16-known-constraints)

---

## 1. Overview

MDViewer is a desktop Markdown viewer built with Python and Tkinter. It renders `.md`
files as GitHub-styled HTML inside a native window, provides a file-system explorer for
navigation, and manages multiple open documents through an Eclipse-inspired overflow tab
system that keeps memory consumption bounded regardless of how many files have been opened.

The application was designed with three goals in mind:

- **Correctness before convenience** — the tab-state model is a pure-Python class with no
  UI dependency, so its invariants can be verified with ordinary unit tests.
- **Replaceability** — the HTML rendering backend is hidden behind a typed Protocol so it
  can be swapped without touching the view layer.
- **Minimal surface area** — configuration, theming, and extension lists are centralised in
  one dataclass; nothing is magic-strung across the codebase.

---

## 2. Technology Stack

| Concern | Library / Tool | Notes |
|---|---|---|
| GUI framework | `tkinter` (stdlib) | Cross-platform, ships with CPython |
| HTML rendering | `tkinterweb` ≥ 4.23 | Wraps tkhtml3 Tcl extension |
| Markdown conversion | `markdown` ≥ 3.7 | Python-Markdown + extensions |
| Packaging | `uv` | Dependency management and virtual environments |
| Executable packaging | `PyInstaller` ≥ 6.3 | `--onefile --windowed` |
| Testing | `pytest` ≥ 8.0 | No additional plugins required |

---

## 3. Project Structure

```
mdviewer/
│
├── main.py                 # Development entry point (delegates to src/main.py)
├── build_exe.py            # PyInstaller build script
├── pyproject.toml          # Project metadata, dependencies, test config
│
├── docs/
│   ├── DEVELOPER-GUIDE.md  # This file
│   └── code-review.md      # Agent-generated code review report
│
├── resources/
│   └── mdviewer.ico        # Optional: application icon for the exe
│
├── tests/
│   ├── conftest.py         # Shared fixtures and sys.path setup
│   ├── test_tab_model.py   # 33 tests for pure-Python tab state
│   └── test_md_converter.py # 18 tests for Markdown conversion
│
└── src/
    ├── main.py             # Application entry point (used by PyInstaller)
    ├── version.py          # Version constants and dynamic copyright year
    ├── config.py           # AppConfig dataclass — single source of truth
    │
    ├── models/
    │   ├── __init__.py
    │   └── tab_model.py    # TabModel + TabData — pure-Python tab state
    │
    ├── resources/
    │   └── github.css      # Externalised GitHub-inspired stylesheet
    │
    ├── utils/
    │   ├── __init__.py
    │   ├── logging_config.py  # Lazy logger + global exception hooks
    │   ├── md_converter.py    # Markdown → HTML pipeline
    │   └── renderer.py        # RendererProtocol + two adapters + factory
    │
    └── views/
        ├── __init__.py
        ├── main_window.py     # Root window, menu, keyboard shortcuts
        ├── file_explorer.py   # Left-panel lazy directory tree
        └── document_viewer.py # Tabbed viewer: _TabBar + DocumentViewer
```

---

## 4. Architecture

### 4.1 Layered overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Views (Tkinter)                       │
│                                                              │
│   MainWindow                                                 │
│   ├── FileExplorer        (left panel, lazy dir tree)        │
│   └── DocumentViewer      (right panel, tabbed)              │
│       ├── _TabBar          (visual-only tab strip)           │
│       └── RendererProtocol (HTML display widget)             │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                       Models (pure Python)                   │
│                                                              │
│   TabModel  ──  TabData                                      │
│   (overflow/promote/demote logic, zero tkinter dependency)   │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                       Utils                                  │
│                                                              │
│   md_converter   renderer   logging_config                   │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                       Config / Version                       │
│                                                              │
│   AppConfig (cfg)   version constants                        │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Component responsibilities

| Component | Owns | Does NOT own |
|---|---|---|
| `TabModel` | Which files are open, which are visible vs overflow, all promote/demote logic | Any widget or rendering |
| `_TabBar` | Visual tab buttons (color, hover, add/remove) | Which files exist, what HTML to show |
| `DocumentViewer` | Coordinating model ↔ tab bar ↔ renderer; overflow button | Tab-state invariants, rendering details |
| `RendererProtocol` adapter | Converting `load_html()` calls to backend-specific API | Tab metadata |
| `FileExplorer` | Lazy filesystem tree; open-file callback | Anything downstream of the callback |
| `MainWindow` | Window layout, menu, keyboard shortcuts, status bar | Tab state, file conversion |

### 4.3 Dependency graph

```
main.py
  └── views/main_window.py
        ├── views/file_explorer.py
        │     └── utils/logging_config.py
        └── views/document_viewer.py
              ├── config.py
              ├── models/tab_model.py   (no further deps)
              ├── utils/md_converter.py
              │     ├── config.py
              │     └── utils/logging_config.py
              └── utils/renderer.py
                    └── utils/logging_config.py

config.py          (no app imports)
version.py         (no app imports)
utils/logging_config.py  (no app imports — fully self-contained)
```

The dependency graph is a strict DAG with no cycles. `config.py`,
`version.py`, and `logging_config.py` are leaves — they import nothing
from the rest of the application.

---

## 5. Module Reference

### 5.1 `src/version.py`

Holds application-level constants that identify the release.

```python
__version__   = "1.0.0"
__copyright__ = f"Copyright (c) {date.today().year} Rohit Gupta"
```

`__copyright__` is computed at import time using `datetime.date.today().year`
so it always reflects the current calendar year without manual updates.

---

### 5.2 `src/config.py`

**Single source of truth** for every tunable value in the application.

```python
from config import cfg

cfg.max_tabs           # int   — visible-tab cap (0 = unlimited)
cfg.log_dir            # Path  — platform-appropriate log directory
cfg.log_level          # str   — "INFO" by default
cfg.theme_css_path     # Path  — path to src/resources/github.css
cfg.tab_color_active   # str   — hex colour for the active tab
cfg.tab_color_inactive # str   — hex colour for inactive tabs
cfg.tab_color_hover    # str   — hex colour on mouse-over
cfg.tab_bar_background # str   — tab strip background
cfg.md_extensions      # list  — Python-Markdown extension module names
```

`cfg` is a module-level singleton instantiated once when `config.py` is first
imported. All other modules reference it via `from config import cfg`.

**To add a new setting:** add a field to `AppConfig` with a default value.
No other files need to be changed to make the setting available.

---

### 5.3 `src/models/tab_model.py`

The core domain model. Contains **no tkinter code**; it can be instantiated and
tested in a pure Python environment.

#### `TabData`

```python
@dataclass
class TabData:
    tab_id:    str   # UUID assigned at creation
    file_path: str   # Absolute, resolved path
    html:      str   # Rendered HTML string
    base_url:  str   # file:// URI of the containing directory
```

Stored in the visible tier of `TabModel`. The overflow tier stores only
`tab_id → file_path` strings to avoid holding large HTML strings in memory
for parked tabs.

#### `TabModel`

Manages the two-tier tab list:

| Tier | Storage | Content |
|---|---|---|
| Visible | `OrderedDict[tab_id, TabData]` | Full rendered HTML; oldest entry first |
| Overflow | `OrderedDict[tab_id, file_path]` | Path only; oldest entry first |

**Key methods:**

| Method | Returns | Description |
|---|---|---|
| `add_visible(data)` | `str \| None` | Adds to visible; returns demoted `tab_id` or `None` |
| `promote(tab_id, html, base_url)` | `str \| None` | Moves overflow → visible; returns demoted `tab_id` or `None` |
| `close_visible(tab_id)` | `str \| None` | Removes from visible; returns auto-promote candidate or `None` |
| `close_overflow(tab_id)` | `None` | Permanently removes a parked tab |
| `close_all_overflow()` | `None` | Clears the entire overflow tier |
| `update_visible_html(tab_id, html, base_url)` | `None` | Replaces stored HTML for a visible tab (refresh) |

All mutation methods return only `tab_id` strings — the caller
(`DocumentViewer`) is responsible for updating the UI accordingly.

---

### 5.4 `src/utils/logging_config.py`

Implements a **lazy-initialised** application logger.

**Why lazy?** Creating a `logging.FileHandler` at import time caused the
`logs/` directory to be created relative to the process working directory,
which placed log files on the Desktop when a user launched the exe via a
shortcut. The fix is to defer initialisation until the first log call.

The public name `logger` is an instance of `_LazyLogger`, a minimal proxy:

```python
class _LazyLogger:
    __slots__ = ()
    def __getattr__(self, name: str):
        return getattr(get_logger(), name)

logger = _LazyLogger()
```

Any attribute access on `logger` (e.g. `logger.info(...)`) transparently
calls `get_logger()` which initialises the real `logging.Logger` on the
first invocation and returns the cached instance on every subsequent call.

**Log location:** `%APPDATA%\MDViewer\logs\mdviewer.log` on Windows;
`~/.local/share/MDViewer/logs/mdviewer.log` fallback on POSIX.

**Rotation:** 5 MB per file, 5 backup files.

---

### 5.5 `src/utils/md_converter.py`

Converts a Markdown file or string to a complete HTML document.

**Pipeline:**

```
File path
  │
  ▼
read_text(encoding="utf-8")
  │  ← UnicodeDecodeError? retry with latin-1 + log warning
  ▼
_get_md().convert(content)        ← cached Markdown instance, reset() between calls
  │
  ▼
_HTML_TEMPLATE.format(css=_get_css(), body=...)
  │  ← CSS loaded from src/resources/github.css, cached after first read
  ▼
Complete HTML string
```

**Caching strategy:**

- `_md_instance` — the `markdown.Markdown` object is created once (loading all
  extensions is expensive) and `.reset()` is called before each conversion to
  clear internal state.
- `_css_cache` — the CSS file is read once; subsequent calls use the in-memory
  string. A fallback inline CSS is used if the file cannot be read.

**Public API:**

```python
convert_md_to_html(file_path: str | Path) -> str
convert_md_string_to_html(md_content: str) -> str
```

---

### 5.6 `src/utils/renderer.py`

Defines the HTML rendering abstraction.

#### `RendererProtocol`

```python
@runtime_checkable
class RendererProtocol(Protocol):
    def load_html(self, html: str, base_url: str = "") -> None: ...
    def get_widget(self) -> tk.Widget: ...
```

Any object that implements these two methods is a valid renderer. `DocumentViewer`
holds a `RendererProtocol` reference and calls only these two methods — it never
imports `tkinterweb` directly.

#### `TkinterwebRenderer`

Wraps `tkinterweb.HtmlFrame`. Handles the API difference between older
tkinterweb versions (where `load_html` does not accept `base_url`) via a
`try/except TypeError` guard.

#### `ScrolledTextRenderer`

Fallback when tkinterweb is unavailable. Strips HTML tags with a regex and
displays the plain Markdown source in a `ScrolledText` widget.

#### `make_renderer(parent) -> RendererProtocol`

Factory function. Returns a `TkinterwebRenderer` if the import succeeds,
otherwise logs a warning and returns a `ScrolledTextRenderer`.

---

### 5.7 `src/views/file_explorer.py`

A lazy-loading directory tree displayed in the left panel.

**Lazy loading** is implemented with a placeholder node technique:

1. When a directory node is inserted, a single child with the tag
   `_TAG_PLACEHOLDER` is added. This causes Tkinter to render the expand arrow.
2. When the user expands the node (`<<TreeviewOpen>>`), the handler checks if
   the only child is the placeholder. If so, it deletes the placeholder and
   calls `_load_children()` to populate real entries.

**Filtering rules:**

- Dot-*directories* (`.kiro`, `.github`, `.git`) are shown — developers often
  need to navigate into them.
- Dot-*files* (`.gitignore`, `.env`) are hidden — they are never `.md` files
  and add clutter.
- Only `.md` and `.markdown` files are shown as leaf nodes.

**Tag constants** (module-level, single source of truth):

```python
_TAG_DIR         = "dir"
_TAG_MD          = "md"
_TAG_PLACEHOLDER = "placeholder"
```

---

### 5.8 `src/views/document_viewer.py`

The most complex view. It coordinates three collaborators:

```
DocumentViewer
    │
    ├── TabModel         (state)
    ├── _TabBar          (visual tab strip)
    └── RendererProtocol (HTML output widget)
```

#### `_TabEntry` dataclass

Replaces the `list[dict]` that originally held tab widget references.
All widget access is now via typed attributes (`entry.outer`, `entry.lbl`,
`entry.close`) rather than magic-string dict keys.

```python
@dataclass
class _TabEntry:
    tab_id: str
    title:  str
    outer:  tk.Frame
    lbl:    tk.Label
    close:  tk.Label
```

#### `_TabBar`

Owns only the visual representation of currently-visible tabs. It has no
knowledge of file paths, HTML content, or overflow state. Its public interface
is exactly three methods: `add(tab_id, title)`, `select(tab_id)`, and
`remove(tab_id) -> str | None` (returns the successor tab_id).

Hover effects are wired in `_on_hover(tab_id, entering)`. The active tab never
changes colour on hover — only inactive tabs use `cfg.tab_color_hover`.

#### `DocumentViewer`

Receives `on_status_update: Callable[[str], None] | None` via its constructor.
This avoids post-construction attribute injection, making the dependency
explicit and preventing silent failures when a tab is evicted before the
parent window has set up the callback.

The `_render_file` method wraps `convert_md_to_html` and catches all exceptions.
Error messages are passed through `html.escape()` before being embedded in the
error HTML to prevent broken output from paths containing `<` or `&`.

---

### 5.9 `src/views/main_window.py`

The root window class. It:

- Constructs the `ttk.PanedWindow` that splits the window horizontally between
  `FileExplorer` and `DocumentViewer`.
- Creates `_status_var` **before** constructing `DocumentViewer` so the lambda
  passed as `on_status_update` is always safe to call.
- Wires `Ctrl+O`, `Ctrl+W`, and `Ctrl+R` keyboard shortcuts at the root level
  (not per-widget) so they work regardless of which widget has focus.

---

### 5.10 `src/main.py`

The application entry point used by PyInstaller.

```python
_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)
```

This `sys.path` manipulation is required for **development** runs
(`python src/main.py`). In a frozen PyInstaller exe, `sys._MEIPASS` is already
in `sys.path`, so the guard has no effect. It is harmless in both environments.

---

## 6. Key Design Patterns

### 6.1 Strategy — `RendererProtocol`

The renderer backend is selected once at startup by `make_renderer()` and
stored as a `RendererProtocol` reference. `DocumentViewer` never branches on
which backend is active — it calls `self._renderer.load_html(html, base_url)`
unconditionally. Adding a third backend (e.g. CEF, WebView2) requires only:
1. Writing a new adapter class that implements `RendererProtocol`.
2. Adding it as a fallback in `make_renderer()`.

No changes to `DocumentViewer` or any other file.

### 6.2 Observer (informal) — status callback

`DocumentViewer` accepts an `on_status_update` callable. When a tab is
evicted to overflow, `_notify()` is called, which invokes the callback if
one was provided. `MainWindow` provides a lambda that sets `_status_var`.
This is a lightweight Observer pattern that decouples the viewer from the
status bar without a full event bus.

### 6.3 Lazy loading — `FileExplorer`

The placeholder-node technique is a classic lazy-loading pattern. The tree
never reads more of the filesystem than the user has explicitly expanded,
keeping startup fast on large directory trees.

### 6.4 Proxy — `_LazyLogger`

`_LazyLogger.__getattr__` delegates every call to the real logger, which is
initialised on first access. This is the Proxy pattern applied to defer an
expensive initialisation (file handle creation, directory creation) without
changing the interface seen by callers.

### 6.5 Factory — `make_renderer`

A simple factory function that encapsulates the `try/except ImportError`
logic for selecting the best available backend. Callers receive a
`RendererProtocol` and never need to know which concrete type they have.

### 6.6 Template Method — `_build_ui`

Each view class (`FileExplorer`, `DocumentViewer`, `MainWindow`) calls
`self._build_ui()` from its constructor. The method is private by convention
and not intended to be overridden, but the pattern establishes a consistent
"construct then configure" lifecycle across all views.

---

## 7. File-to-Screen: Full Call Stack

This section traces every function call that occurs from the moment the user
double-clicks a `.md` file in the explorer until pixels appear on screen.
Each frame in the call stack is annotated with its file, its role, and any
important decisions it makes.

```
USER double-clicks "DEVELOPER-GUIDE.md" in the tree
│
│  [views/file_explorer.py]
▼
FileExplorer._on_double_click(event)
│  Reads the row that was clicked via self._tree.identify_row(event.y).
│  Checks the row's tag — only _TAG_MD rows trigger an open.
│  Extracts the file path from the row's values tuple.
│  Calls the injected callback.
│
│  [views/main_window.py]
▼
MainWindow._open_file(file_path)
│  Logs "Opening: <filename>" at INFO level.
│  Updates the status bar StringVar with the filename.
│  Delegates to the viewer.
│
│  [views/document_viewer.py]
▼
DocumentViewer.open_file(file_path)
│  Resolves the path to an absolute string via Path.resolve().
│  ┌─ Already open? ──────────────────────────────────────────────────┐
│  │  TabModel.is_open(path) → True                                   │
│  │    If visible  → _select_visible(tab_id)   switch + load HTML    │
│  │    If overflow → _promote(tab_id)          reload from disk      │
│  │  Either way, returns early.                                       │
│  └──────────────────────────────────────────────────────────────────┘
│  First open: calls _render_file(path) ...
│
│  [views/document_viewer.py]
▼
DocumentViewer._render_file(file_path)
│  Wraps the converter in a try/except — returns an error HTML page
│  on failure rather than propagating the exception to the UI.
│  Calls convert_md_to_html and builds the base_url.
│
│  [utils/md_converter.py]
▼
md_converter.convert_md_to_html(file_path)
│  Reads the file:
│    path.read_text(encoding="utf-8")
│    └─ UnicodeDecodeError? → retry latin-1, log warning
│
│  Converts to HTML body:
│    _get_md().convert(content)
│    │  _get_md() returns the cached markdown.Markdown instance,
│    │  calling .reset() to clear TOC/footnote state from the
│    │  previous file before reuse.
│    └─ Extensions active: tables, fenced_code, toc, nl2br,
│       attr_list, def_list, footnotes  (from cfg.md_extensions)
│
│  Wraps in HTML document:
│    _HTML_TEMPLATE.format(css=_get_css(), body=html_body)
│    │  _get_css() reads src/resources/github.css on first call,
│    │  then returns the cached string on all subsequent calls.
│    └─ Returns a complete <!DOCTYPE html> ... </html> string
│
│  returns (html_string, "file:///path/to/dir/")
│         ↑                    ↑
│         HTML document        base_url = parent directory as file:// URI
│
│  [views/document_viewer.py]
▼
DocumentViewer.open_file  (continued)
│  Constructs TabData(tab_id=uuid4(), file_path, html, base_url).
│
│  TabModel.add_visible(data)
│  │  Checks len(_vis) against max_visible (default 5).
│  │  If at cap: calls _demote_oldest()
│  │    ├─ Pops oldest entry from _vis (OrderedDict, so front = oldest)
│  │    ├─ Stores tab_id → file_path in _ovf (path only; HTML discarded)
│  │    └─ Returns the demoted tab_id to the caller
│  │  Stores new TabData in _vis[tab_id].
│  │  Records path → tab_id in _path_tab.
│  └─ Returns demoted_id or None
│
│  If demoted_id:
│    _TabBar.remove(demoted_id)   ← destroys the tab button widget
│    _notify("… moved to overflow …")  ← status bar via on_status_update
│
│  _TabBar.add(tab_id, "DEVELOPER-GUIDE.md")
│  │  Creates tk.Frame (outer container) + tk.Label (title) +
│  │  tk.Label (× close button).
│  │  Binds <Button-1> → _on_select, <Button-2> → _on_close,
│  │       <Enter>/<Leave> → _on_hover for all three widgets.
│  └─ Calls _highlight(tab_id): sets active_id, recolours all tabs.
│
│  [views/document_viewer.py → utils/renderer.py]
▼
DocumentViewer calls: self._renderer.load_html(html, base_url)
│  self._renderer is a TkinterwebRenderer (RendererProtocol).
│
│  [utils/renderer.py]
▼
TkinterwebRenderer.load_html(html, base_url)
│
│  Step 1 — Rewrite relative URLs to absolute:
│    _make_urls_absolute(html, base_url)
│    │  Scans every src="…" and href="…" in the HTML.
│    │  Anchors (#…), external URLs (http/https), data: URIs → unchanged.
│    │  Relative paths (e.g. "image.png") →
│    │      urljoin(base_url, "image.png")
│    │      = "file:///path/to/dir/image.png"   (absolute)
│    └─ Returns modified HTML string
│
│  Step 2 — Write to temp file:
│    TkinterwebRenderer._TEMP_FILE.write_text(html, encoding="utf-8")
│    │  Path: %TEMP%/mdviewer_render/current.html
│    │  Shared across all tabs (overwritten on every load_html call).
│    │  Required so tkinterweb has a real current URL, which is
│    │  necessary for in-document anchor navigation to work.
│    └─ See § 10 for the full explanation of why this is needed.
│
│  Step 3 — Load via URL (not via string):
│    self._frame.load_url(temp_file.as_uri())
│    │  temp_file.as_uri() → "file:///C:/Users/…/mdviewer_render/current.html"
│    │  This call goes directly to the original tkinterweb load_url,
│    │  bypassing on_link_click (which is only for user click events).
│    └─ tkinterweb reads the temp file, parses HTML/CSS, renders to screen.
│
▼
HtmlFrame renders the HTML to the tkinter canvas.
Pixels appear on screen. ✓
```

### 7.1 What happens when the user clicks a TOC anchor link

After the document is on screen, clicking `<a href="#7-file-to-screen-full-call-stack">`
triggers a second, shorter call chain:

```
USER clicks a TOC anchor link
│
│  [tkinterweb internals — Tcl/Tk level]
▼
tkinterweb detects the click and fires the on_link_click callback
with the resolved URL.
│
│  Anchor "#section" resolved against current URL
│  (file:///…/current.html) → "file:///…/current.html#section"
│
│  [utils/renderer.py]
▼
TkinterwebRenderer._handle_link_click(url)
│  url = "file:///…/mdviewer_render/current.html#7-file-to-screen-…"
│
│  Not http/https → skip external-browser branch.
│
│  Starts with "file://" → parse local path:
│    _file_url_to_path(url)
│    │  urlparse strips the fragment: path = "…/current.html"
│    └─ Returns "C:/…/mdviewer_render/current.html"
│
│  Path("…/current.html").suffix = ".html"
│  Not empty  → not suppressed (bare dir check passes)
│  Not .md    → not a cross-file link
│
│  Falls through to: self._frame.load_url(url)
│  │  url still includes the fragment: "…/current.html#section"
│  │  tkinterweb re-loads current.html (from OS cache, instant)
│  └─ Scrolls to the element with id="section". ✓
│
▼
Page scrolls to the target heading. No navigation, no "Oops".
```

### 7.2 What happens when the user clicks an external link

```
USER clicks <a href="https://github.com/g-ro/mdviewer">
│
▼
TkinterwebRenderer._handle_link_click("https://github.com/g-ro/mdviewer")
│  Starts with "https://" → webbrowser.open(url)
└─ System default browser opens the URL.
   tkinterweb never navigates. Page stays on screen. ✓
```

---

## 8. Data Flow Walkthrough

This section traces what happens when the user double-clicks `README.md` in
the file explorer, assuming 4 tabs are already open (one slot remaining before
the cap is hit).

```
1. FileExplorer._on_double_click(event)
      │ calls
      ▼
2. MainWindow._open_file("/path/to/README.md")
      │ calls
      ▼
3. DocumentViewer.open_file("/path/to/README.md")
      │
      ├─ TabModel.is_open("/path/to/README.md")  → False  (not yet open)
      │
      ├─ _render_file("/path/to/README.md")
      │     ├─ md_converter.convert_md_to_html(path)
      │     │     ├─ path.read_text(encoding="utf-8")
      │     │     ├─ _get_md().convert(content)   ← cached Markdown instance
      │     │     └─ _HTML_TEMPLATE.format(css=_get_css(), body=...)
      │     └─ returns (html_string, "file:///path/to/")
      │
      ├─ data = TabData(tab_id=uuid4(), file_path=..., html=..., base_url=...)
      │
      ├─ TabModel.add_visible(data)
      │     ├─ len(_vis)=4 < max_visible=5 → no demotion needed
      │     ├─ _vis[tab_id] = data
      │     └─ returns None
      │
      ├─ _TabBar.add(tab_id, "README.md")
      │     ├─ Creates Frame + Label + close Label widgets
      │     ├─ Wires click/hover bindings
      │     └─ Calls _highlight(tab_id) → sets active_id, recolours all tabs
      │
      ├─ RendererProtocol.load_html(html, "file:///path/to/")
      │     └─ TkinterwebRenderer._frame.load_html(html, base_url=...)
      │
      └─ _update_overflow_btn()
            └─ overflow_count=0 → ovf_btn.grid_remove()  (hidden)
```

**With overflow (6th file, 5 already open):**

Step 3 changes at `TabModel.add_visible(data)`:
```
├─ TabModel.add_visible(data)
│     ├─ len(_vis)=5 == max_visible=5 → calls _demote_oldest()
│     │     ├─ oldest_id, oldest_data = next(iter(_vis.items()))
│     │     ├─ del _vis[oldest_id]
│     │     ├─ _ovf[oldest_id] = oldest_data.file_path
│     │     └─ returns oldest_id
│     ├─ _vis[new_tab_id] = data
│     └─ returns oldest_id
│
├─ _TabBar.remove(oldest_id)         ← removes oldest tab widget
├─ _notify("… moved to overflow …")  ← status bar update
├─ _TabBar.add(new_tab_id, "README.md")
├─ RendererProtocol.load_html(...)
└─ _update_overflow_btn()
       └─ overflow_count=1 → ovf_btn.configure(text="»  1"); ovf_btn.grid()
```

---

## 9. The Tab Lifecycle

### States

Each file tracked by `TabModel` is in exactly one of three states:

```
         open_file()              add_visible() + cap reached
NOT OPEN ──────────► VISIBLE ───────────────────────────────► OVERFLOW
                        │                                        │
                        │  close_visible()                       │  _promote()
                        │                                        │
                        ▼                                        ▼
                      GONE ◄─────────────────────────────── VISIBLE
                              close_overflow()               (reload from disk)
```

### Invariants maintained by `TabModel`

1. Every path in `_path_tab` maps to exactly one `tab_id`.
2. No `tab_id` appears in both `_vis` and `_ovf` simultaneously.
3. `len(_vis) ≤ max_visible` when `max_visible > 0`.
4. When a tab is promoted, it carries its original `tab_id` (the path-to-id
   mapping is never reassigned for the same path).

### Auto-promotion on close

When the user closes a visible tab and overflow is non-empty, `close_visible()`
returns the most-recently-parked overflow `tab_id`. `DocumentViewer._close_visible()`
immediately calls `_promote()` on it, keeping the visible tier as full as possible.
This mirrors Eclipse's behaviour: closing a tab causes the previously-hidden tab
to "pop back" automatically.

---

---

## 10. HTML Rendering: Problems and Solutions

This section documents the sequence of failures encountered when implementing
link navigation in the HTML renderer, and the reasoning that led to the final
solution. It is preserved here because the problems are non-obvious, the fixes
are counter-intuitive, and any developer touching `renderer.py` should
understand the design before changing it.

---

### 10.1 Background: how tkinterweb handles link clicks

`tkinterweb.HtmlFrame` is a Python wrapper around the `tkhtml3` Tcl/Tk
widget. When the user clicks a hyperlink, the Tcl layer detects the event and
invokes a registered Python callback. That callback is configured at
construction time as `on_link_click`, and its **default value is
`self.load_url`**.

This means the routing chain for a link click is:

```
User clicks link
    │
    ▼  [Tcl level]
tkhtml3 fires the registered Python callback
    │
    ▼  [Python level]
on_link_click(url)   ← set once at HtmlFrame construction
    │
    ▼
load_url(url)        ← default; navigates the HtmlFrame to url
```

Understanding this chain is the key to all three problems below.

---

### 10.2 Problem 1 — "Oops" page on every link click

**Symptom:** Clicking any hyperlink in a rendered document caused the document
to disappear and be replaced by tkinterweb's built-in error page:
> *Oops — The page you've requested could not be found*

**Root cause:** The `on_link_click` callback defaults to `load_url`. For
external `https://` URLs, tkinterweb tried to fetch the page and failed
(no HTTP client is configured). For in-document anchor links like
`<a href="#section">`, the `toc` Markdown extension generates heading IDs,
and the link gets resolved against `base_url`. Since `base_url` was set to
the containing *directory* (`file:///C:/docs/`), `#section` resolved to
`file:///C:/docs/#section` — a directory path with a fragment. tkinterweb
cannot open a directory as a web page, so it showed "Oops".

**First attempt (wrong):** Monkey-patch `frame.load_url` after construction:

```python
original = frame.load_url
def guarded(url, **kw):
    if should_intercept(url):
        return
    original(url, **kw)
frame.load_url = guarded   # ← This does NOT work
```

This failed because `on_link_click` is stored at construction time as a
reference to the *original* `load_url` method. Replacing the instance
attribute afterwards has no effect — the stored callback still points to
the original.

**Diagnostic that revealed the real API:**

```python
import inspect
src = inspect.getsource(type(frame))
for line in src.split('\n'):
    if 'link' in line.lower():
        print(line)
# Output included:
# on_link_click: The function to be called when a hyperlink is clicked.
# "on_link_click": {"default": self.load_url, "type": "callable"},
```

**Fix:** Pass the interception handler at construction time:

```python
HtmlFrame(parent, on_link_click=self._handle_link_click, ...)
```

**Result:** The "Oops" page was eliminated for external links. Clicking
`https://...` links now opened the system browser. Anchor links still did
nothing (see Problem 2).

---

### 10.3 Problem 2 — Anchor links did nothing after first fix

**Symptom:** After fixing Problem 1, clicking TOC anchor links (`#section`)
no longer showed "Oops" but also did not scroll to the target section. The
page simply did not respond.

**Root cause:** Our `_handle_link_click` suppressed any `file://` URL with no
file extension (which correctly matched `file:///C:/docs/#section` since the
path component had no extension). This prevented the error but also silently
swallowed the scroll intent.

The real issue was deeper: we were using `frame.load_html(html, base_url)`
to render the page. When `load_html` is used, `HtmlFrame` has no concept of a
"current URL" — the document exists purely as an in-memory string. So when
the user clicks `<a href="#section">`, tkinterweb has no file URL to resolve
the fragment against, and anchor navigation cannot work at all.

**Analogy:** It is like opening an HTML file from a string in a browser that
has no address bar. The browser cannot jump to `#section` because it does not
know what file it is showing.

---

### 10.4 Problem 3 — Relative images break when using a temp file naively

The natural fix for Problem 2 is to write the HTML to a temp file and use
`load_url("file:///temp/current.html")` instead of `load_html()`. Then:
- `#section` resolves to `file:///temp/current.html#section`
- `.html` extension → falls through our interceptor to `load_url`
- tkinterweb scrolls to the anchor ✓

**But:** images and other relative resources in the original document
(e.g. `<img src="diagram.png">`) resolve against the temp file's directory,
not the original document's directory. They would look for
`%TEMP%/mdviewer_render/diagram.png` which does not exist.

---

### 10.5 Final solution — temp file + pre-processed absolute URLs

**The insight:** decouple the two concerns:

| Concern | Solution |
|---|---|
| Anchor navigation needs a current URL | Write to temp file, load via `load_url` |
| Relative resources need original directory | Rewrite relative URLs to absolute *before* writing |

**Step 1 — Pre-process:** `_make_urls_absolute(html, base_url)` scans every
`src=` and `href=` attribute in the HTML and rewrites relative values to
absolute `file://` URLs using `urljoin(base_url, url)`.

```python
_ATTR_RE = re.compile(r'(src|href)\s*=\s*(["\'])([^"\']*?)\2', re.IGNORECASE)

def _make_urls_absolute(html: str, base_url: str) -> str:
    def _replace(m):
        attr, quote, url = m.group(1), m.group(2), m.group(3)
        if not url or url.startswith(("#", "http", "data:", "file://", "mailto:")):
            return m.group(0)   # leave unchanged
        return f'{attr}={quote}{urljoin(base_url, url)}{quote}'
    return _ATTR_RE.sub(_replace, html)
```

Crucially, **anchor links (`#section`) are left unchanged** because they start
with `#`. After this step:

| Original | After |
|---|---|
| `src="diagram.png"` | `src="file:///C:/docs/diagram.png"` — absolute ✓ |
| `href="other.md"` | `href="file:///C:/docs/other.md"` — absolute ✓ |
| `href="#section"` | `href="#section"` — unchanged (resolved later) ✓ |
| `href="https://…"` | `href="https://…"` — unchanged ✓ |

**Step 2 — Write and load:**

```python
self._TEMP_FILE.write_text(html, encoding="utf-8")
self._frame.load_url(self._TEMP_FILE.as_uri())
```

**Step 3 — Anchor click routing:**

When the user clicks `#section`, tkinterweb resolves it against the temp
file's URI → `file:///…/current.html#section`. Our handler sees:

- Extension = `.html` → not suppressed, not `.md`
- Falls through to `self._frame.load_url(url)`
- tkinterweb reloads the temp file (from OS cache, instant) + scrolls ✓

**Complete URL routing table (final):**

```
file:///…/current.html#section  →  .html ext  →  load_url  →  scroll ✓
file:///C:/docs/other.md        →  .md ext    →  on_navigate → new tab ✓
file:///C:/docs/img.png         →  .png ext   →  load_url  →  image loads ✓
file:///C:/docs/                →  no ext     →  suppressed  →  no-op ✓
https://example.com             →  http*      →  browser ✓
```

---

### 10.6 Lessons for future changes to `renderer.py`

1. **Never intercept by wrapping `load_url` after construction.** The
   `on_link_click` callback is stored at construction time. Use the
   constructor parameter.

2. **Never use `load_html()` when anchor navigation must work.** Always
   write to the temp file and use `load_url()`.

3. **Pre-process relative URLs before writing to temp file.** The temp file
   lives in a different directory from the original; relative paths will
   resolve wrongly without `_make_urls_absolute`.

4. **Identify no-extension `file://` paths as safe-to-suppress.** They
   arise from the markdown `toc` extension generating `#anchor` links that
   get resolved against a `base_url` pointing to a directory. No file at that
   path exists; suppressing silently is correct.

5. **Do not change `_TEMP_FILE` to be per-tab.** It is intentionally shared:
   there is only one `HtmlFrame` instance, and it always shows exactly one
   document. Per-tab temp files would consume disk space unnecessarily.

---

## 11. Configuration Reference

All settings live in `src/config.py` inside the `AppConfig` dataclass.
Import the singleton:

```python
from config import cfg
```

| Field | Type | Default | Description |
|---|---|---|---|
| `max_tabs` | `int` | `5` | Maximum simultaneously visible (rendered) tabs. `0` = no limit. |
| `log_dir` | `Path` | `%APPDATA%\MDViewer\logs` | Log file directory. Created lazily on first log write. |
| `log_level` | `str` | `"INFO"` | Standard Python logging level name. |
| `theme_css_path` | `Path` | `src/resources/github.css` | Path to the Markdown stylesheet. User-replaceable. |
| `tab_color_active` | `str` | `"#ffffff"` | Background colour of the active tab button. |
| `tab_color_inactive` | `str` | `"#d0d0d0"` | Background colour of inactive tab buttons. |
| `tab_color_hover` | `str` | `"#ebebeb"` | Background colour on mouse-over (inactive tabs only). |
| `tab_bar_background` | `str` | `"#b8b8b8"` | Tab strip container background. |
| `md_extensions` | `list[str]` | See below | Python-Markdown extension module names. |

**Default `md_extensions`:**

```python
[
    "markdown.extensions.tables",
    "markdown.extensions.fenced_code",
    "markdown.extensions.toc",
    "markdown.extensions.nl2br",
    "markdown.extensions.attr_list",
    "markdown.extensions.def_list",
    "markdown.extensions.footnotes",
]
```

To add a Markdown extension (e.g. `pymdownx.superfences`), append it to
`cfg.md_extensions` before the application window is created — or subclass
`AppConfig` and replace the `cfg` singleton.

---

## 12. Extending the Application

### 10.1 Adding a new HTML renderer backend

1. Create a class that implements `RendererProtocol`:

```python
# src/utils/renderer.py  (or a new file)
class MyCustomRenderer:
    def __init__(self, parent: tk.Widget) -> None:
        # create your widget here
        self._widget = ...

    def load_html(self, html: str, base_url: str = "") -> None:
        # display the html
        ...

    def get_widget(self) -> tk.Widget:
        return self._widget
```

2. Register it in `make_renderer()`:

```python
def make_renderer(parent: tk.Widget) -> RendererProtocol:
    try:
        return TkinterwebRenderer(parent)
    except ImportError:
        try:
            return MyCustomRenderer(parent)
        except ImportError:
            logger.warning("falling back to plain-text renderer")
            return ScrolledTextRenderer(parent)
```

No other files need to change.

### 10.2 Adding a new panel to the main window

1. Create a new `ttk.Frame` subclass in `src/views/`.
2. In `MainWindow.__init__`, add it to the `ttk.PanedWindow`:

```python
self.my_panel = MyPanel(paned)
paned.add(self.my_panel, weight=1)
```

3. Wire any cross-panel communication through callbacks passed at
   construction time, following the same pattern as `on_file_open` in
   `FileExplorer` and `on_status_update` in `DocumentViewer`.

### 10.3 Changing the Markdown theme

Replace `src/resources/github.css` with any CSS you like. No code changes
are required. The new CSS is picked up on next launch (or next call to
`convert_md_to_html` after the cache is cleared).

To clear the CSS cache at runtime:

```python
import utils.md_converter as mc
mc._css_cache = None   # next conversion will re-read the file
```

### 10.4 Adding a new configuration field

Add a field to `AppConfig` in `src/config.py`:

```python
@dataclass
class AppConfig:
    ...
    show_line_numbers: bool = False
```

The field is immediately available as `cfg.show_line_numbers` everywhere
`from config import cfg` is in scope. No registration or plumbing needed.

### 10.5 Implementing undo / redo

The `TabModel` mutation methods already return the information needed to
reverse an operation (demoted `tab_id`, auto-promote candidate). A Command
pattern stack could be built on top without modifying `TabModel`:

```python
@dataclass
class OpenFileCommand:
    tab_id:     str
    file_path:  str
    demoted_id: str | None   # returned by add_visible()

class CommandHistory:
    _stack: list[OpenFileCommand] = field(default_factory=list)

    def push(self, cmd: OpenFileCommand): ...
    def undo(self, model: TabModel, viewer: DocumentViewer): ...
```

---

## 13. Testing

### 11.1 Running tests

```bash
# Install test dependencies
uv sync --group test

# Run all tests
uv run --group test pytest tests/

# Run with verbose output
uv run --group test pytest tests/ -v

# Run a specific test class
uv run --group test pytest tests/test_tab_model.py::TestPromote -v
```

### 11.2 Test structure

```
tests/
├── conftest.py
│     └── tmp_md_file fixture — creates temp .md files with custom encoding
│
├── test_tab_model.py          (33 tests, 0 tkinter dependency)
│     TestAddVisible            cap enforcement, LRU demotion, cap=0 mode
│     TestQueries               is_open, is_visible, overflow_items order
│     TestPromote               promote mechanics, cascade demotion, invalid id
│     TestCloseVisible          path registry cleanup, auto-promote candidate
│     TestCloseOverflow         single close, close-all, empty guard
│     TestUpdateVisibleHtml     refresh in-place
│
└── test_md_converter.py       (18 tests)
      TestHtmlStructure         DOCTYPE, head/body, CSS, charset
      TestUtf8Conversion        headings, bold, italic, Path/str equivalence
      TestLatin1Fallback        graceful recovery, content decoded
      TestExtensions            tables, fenced code
      TestConvertString         string API, complete document, empty input
      TestErrorCases            FileNotFoundError propagation
      TestCachedInstanceReset   no state bleed between calls, idempotent
```

### 11.3 What is NOT currently tested

| Area | Reason | How to test it |
|---|---|---|
| `FileExplorer` | Requires a `tk.Tk()` root | Use `pytest-tk` or mock `ttk.Treeview` |
| `DocumentViewer` | Requires tkinter + renderer | Integration test with headless display (Xvfb on Linux) |
| `_TabBar` | Widget creation needs Tk | Same as above |
| `make_renderer` | ImportError branch | Mock `tkinterweb` with `unittest.mock` |

### 11.4 Adding a new test

1. Create `tests/test_<module>.py`.
2. Add `sys.path` is already configured by `conftest.py` — no extra setup needed.
3. Import the module under test directly:

```python
from models.tab_model import TabModel, TabData
from utils.md_converter import convert_md_to_html
```

4. Use the `tmp_md_file` fixture from `conftest.py` to create temporary
   Markdown files with controlled content.

---

## 14. Building the Executable

### 12.1 Prerequisites

```bash
uv sync --group build
```

This installs `PyInstaller` into the virtualenv.

### 12.2 Running the build

```bash
uv run --group build python build_exe.py
```

Output: `dist/MDViewer.exe` — a self-contained single-file executable.

### 12.3 How the build script works

`build_exe.py` invokes `PyInstaller.__main__.run()` directly (no subprocess).
Key arguments:

| Argument | Purpose |
|---|---|
| `--paths={src_dir}` | Tells PyInstaller to treat `src/` as a module root during analysis so `views.*`, `utils.*`, and `config` are discovered correctly |
| `--collect-all=tkinterweb` | Bundles the Tcl/Tk HTML widget DLL and supporting files |
| `--collect-all=markdown` | Bundles all Python-Markdown extension modules |
| `--add-data=src/resources;resources` | Copies `github.css` into the exe bundle at the `resources/` path where `AppConfig._default_css_path()` expects it |
| `--hidden-import=...` | Belt-and-suspenders declarations for all app modules |
| `--onefile --windowed` | Single executable, no console window |

### 12.4 Adding a custom icon

Place `mdviewer.ico` in the `resources/` directory (the one at the project
root, not `src/resources/`). The build script checks for it automatically:

```python
icon_path = os.path.join(script_dir, "resources", "mdviewer.ico")
icon_args = [f"--icon={icon_path}"] if os.path.exists(icon_path) else []
```

### 12.5 Debugging a failed build

The most common failure mode is `ModuleNotFoundError` at runtime. Check:

1. `--paths={src_dir}` is present (covers `views.*`, `utils.*`, `config`).
2. Any new module added to `src/` has a corresponding `--hidden-import` entry.
3. Any new data file in `src/resources/` has a corresponding `--add-data` entry.

---

## 15. Development Workflow

### 13.1 Initial setup

```bash
git clone git@github.com:g-ro/mdviewer.git
cd mdviewer
uv sync          # installs runtime deps
uv sync --group test   # also installs pytest
uv sync --group build  # also installs PyInstaller
```

### 13.2 Running in development

```bash
uv run python main.py
```

The root `main.py` uses `importlib.util.spec_from_file_location` to load
`src/main.py` under a distinct module name, avoiding a naming collision with
the root file itself.

Alternatively, run the entry point directly:

```bash
uv run python src/main.py
```

### 13.3 Making changes to the tab model

`TabModel` has no UI dependency. Make your change, run the tests:

```bash
uv run --group test pytest tests/test_tab_model.py -v
```

If the logic change affects the UI (e.g. a new return value from a mutation
method), update the corresponding handler in `DocumentViewer` accordingly.

### 13.4 Making changes to the CSS theme

Edit `src/resources/github.css`. Restart the application — the CSS file is
read on the first conversion call and cached. Alternatively call
`mc._css_cache = None` in a Python REPL attached to the running process.

### 13.5 Changing the tab cap

Edit `MAX_TABS` in `src/config.py`:

```python
max_tabs: int = 5   # change this
```

All overflow/eviction logic reads from `cfg.max_tabs`; no other changes needed.

---

## 16. Known Constraints

| Constraint | Impact | Notes |
|---|---|---|
| Single `HtmlFrame` instance | All tabs share one rendered page — switching tabs triggers a full `load_html()` call | Creating multiple `HtmlFrame` instances crashes the process on Windows due to global state in the tkhtml3 Tcl extension |
| `tkinterweb` is Windows/Linux only | macOS builds are unsupported | The `ScrolledTextRenderer` fallback works everywhere |
| No async rendering | Large files briefly freeze the UI during conversion | `convert_md_to_html` is synchronous; moving it to a `threading.Thread` would require careful `after()` callback wiring |
| Scroll position not preserved | Switching tabs resets scroll to top | Would require per-tab scroll state stored in `TabData` and a mechanism to restore it after `load_html()` |
| No live file-watching | Edits to an open file are not reflected until the user presses `Ctrl+R` | Could be added with `watchdog` library — it would call `DocumentViewer.refresh_current_tab()` on file-change events |
| PyInstaller `--onefile` startup time | The exe takes 2–5 seconds on first launch while extracting to temp dir | Normal for `--onefile` PyInstaller; use `--onedir` for faster launch at the cost of a folder instead of a single exe |

---

*End of Developer Guide*
