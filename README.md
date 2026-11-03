# MDViewer

A tabbed Markdown file viewer built with Python + Tkinter.

## Features

- **File explorer** — browse any directory, shows `.md` / `.markdown` files
- **Tabbed interface** — open multiple documents side by side
- **GitHub-styled rendering** — rendered via `tkinterweb` with a clean CSS theme
- **Tab management** — middle-click or right-click → Close; `Ctrl+W` keyboard shortcut
- **Refresh** — `Ctrl+R` or the toolbar button re-reads the file from disk
- **Link handling** — local `.md` links open as new tabs; external links open in the system browser

## Running (development)

```bash
uv sync
uv run python main.py
```

Or directly:

```bash
uv run python src/main.py
```

## Building the executable

```bash
# Install build dependencies first
uv sync --group build

# Build
uv run python build_exe.py
```

The output will be `dist/MDViewer.exe` — a single self-contained Windows executable.

## Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open file |
| `Ctrl+W` | Close current tab |
| `Ctrl+R` | Refresh current tab |

## Project layout

```
mdviewer/
├── main.py              # Dev entry point
├── pyproject.toml
├── build_exe.py         # PyInstaller build script
├── resources/           # Place mdviewer.ico here for a custom icon
└── src/
    ├── main.py          # Application entry point
    ├── version.py
    ├── views/
    │   ├── main_window.py
    │   ├── file_explorer.py
    │   └── document_viewer.py
    └── utils/
        ├── logging_config.py
        └── md_converter.py
```
