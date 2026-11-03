# MDViewer

> A fast, tabbed Markdown viewer for the desktop — built with Python and Tkinter.

MDViewer renders `.md` files as clean, GitHub-styled HTML inside a native window.
Open as many files as you like; the Eclipse-inspired overflow tab system keeps
memory bounded while making sure you never lose track of a document.

---

## Features

| | |
|---|---|
| 📁 **File explorer** | Browse any directory; only `.md` / `.markdown` files are shown. Dot-directories (`.kiro`, `.github`, …) are included. |
| 🗂️ **Tabbed interface** | Open multiple documents side by side. |
| 🔄 **Overflow tabs** | When the visible-tab limit (default 5) is reached the oldest tab is quietly parked behind a **» N** button — its path is remembered but its HTML is freed. Click the button to bring any parked tab back instantly. |
| 🎨 **GitHub-styled rendering** | Converted via the `markdown` library; rendered by `tkinterweb` with a clean CSS theme. Tables, fenced code blocks, footnotes, and TOC are all supported. |
| 🔗 **Smart link handling** | Local `.md` links open as new tabs; external `http(s)` links open in the system browser. |
| ↺ **Refresh** | `Ctrl+R` or the toolbar button re-reads the file from disk — useful while editing. |
| ⌨️ **Keyboard shortcuts** | `Ctrl+O` open file · `Ctrl+W` close tab · `Ctrl+R` refresh |
| 📦 **Single-file executable** | Ships as a self-contained `MDViewer.exe` via PyInstaller — no Python installation required for end users. |

---

## Screenshots

> _Add a screenshot here once the app is running._

---

## Requirements

- Python **3.13+**
- [uv](https://docs.astral.sh/uv/) package manager

Runtime dependencies (installed automatically via `uv sync`):

| Package | Purpose |
|---|---|
| [`markdown`](https://python-markdown.github.io/) | Converts Markdown to HTML |
| [`tkinterweb`](https://github.com/Andereoo/TkinterWeb) | Renders HTML inside a Tkinter widget |

---

## Getting started

```bash
# Clone
git clone git@github.com:g-ro/mdviewer.git
cd mdviewer

# Install dependencies
uv sync

# Run
uv run python main.py
```

---

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+O` | Open a Markdown file via dialog |
| `Ctrl+W` | Close the current tab |
| `Ctrl+R` | Refresh (reload from disk) |

---

## Tab overflow system

MDViewer keeps at most **5 visible (rendered) tabs** at a time.
When you open a 6th file the oldest visible tab is *demoted* — its HTML is
discarded to free memory, but its file path is retained.

A **» N** button appears at the right end of the tab strip, where N is the
count of parked tabs. Clicking it shows a dropdown of all parked files.
Selecting one *promotes* it back to the front: the file is reloaded from disk
and the oldest current visible tab is demoted in its place.

Closing a visible tab with **×** frees it entirely. If there are parked tabs
the most-recently-parked one is automatically promoted to fill the slot.

The limit is a single constant at the top of `src/views/document_viewer.py`:

```python
MAX_TABS: int = 5   # set to 0 to disable the limit
```

---

## Building the executable

```bash
# Install build dependencies (PyInstaller)
uv sync --group build

# Build
uv run --group build python build_exe.py
```

Output: `dist/MDViewer.exe` — a single self-contained Windows executable.

To add a custom icon, place `mdviewer.ico` in the `resources/` directory before
running the build.

---

## Project structure

```
mdviewer/
├── main.py              # Development entry point
├── build_exe.py         # PyInstaller build script
├── pyproject.toml       # Project metadata and dependencies
├── resources/           # Place mdviewer.ico here for a custom exe icon
└── src/
    ├── main.py          # Application entry point (used by PyInstaller)
    ├── version.py       # Version and metadata constants
    ├── views/
    │   ├── main_window.py       # Root window, menu, layout
    │   ├── file_explorer.py     # Left-panel directory tree
    │   └── document_viewer.py   # Tab bar, overflow system, HTML renderer
    └── utils/
        ├── logging_config.py    # Rotating file + console logger
        └── md_converter.py      # Markdown → HTML with GitHub CSS
```

---

## How it works

1. `file_explorer.py` walks the file system lazily (directories expand on click).
2. Double-clicking a `.md` file calls `DocumentViewer.open_file()`.
3. `md_converter.py` reads the file and converts it to a full HTML document with
   embedded GitHub-inspired CSS.
4. The single shared `HtmlFrame` (from `tkinterweb`) calls `load_html()` with the
   new content — only one HtmlFrame instance ever exists, which prevents a known
   tkinterweb crash when multiple instances are created simultaneously.

---

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.

---

## Author

**Rohit Gupta** — [github.com/g-ro](https://github.com/g-ro)
