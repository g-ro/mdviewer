#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Markdown to HTML converter with GitHub-inspired styling."""
import markdown
from pathlib import Path

_GITHUB_CSS = """
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    font-size: 15px;
    line-height: 1.6;
    color: #24292e;
    background-color: #ffffff;
    padding: 24px 40px;
    margin: 0;
    max-width: 960px;
    box-sizing: border-box;
}
h1, h2 {
    border-bottom: 1px solid #eaecef;
    padding-bottom: 0.3em;
    margin-top: 24px;
    margin-bottom: 16px;
    font-weight: 600;
}
h1 { font-size: 2em; }
h2 { font-size: 1.5em; }
h3 { font-size: 1.25em; margin-top: 24px; margin-bottom: 16px; font-weight: 600; }
h4 { font-size: 1em; margin-top: 24px; margin-bottom: 16px; font-weight: 600; }
h5 { font-size: 0.875em; margin-top: 24px; margin-bottom: 16px; font-weight: 600; }
h6 { font-size: 0.85em; color: #6a737d; margin-top: 24px; margin-bottom: 16px; font-weight: 600; }
p { margin-top: 0; margin-bottom: 16px; }
a { color: #0366d6; text-decoration: none; }
a:hover { text-decoration: underline; }
code {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 85%;
    background-color: rgba(27,31,35,0.05);
    padding: 0.2em 0.4em;
    border-radius: 3px;
}
pre {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 85%;
    background-color: #f6f8fa;
    padding: 16px;
    overflow: auto;
    border-radius: 6px;
    line-height: 1.45;
    margin-top: 0;
    margin-bottom: 16px;
    word-wrap: normal;
}
pre code {
    background: none;
    padding: 0;
    font-size: 100%;
    white-space: pre;
    border-radius: 0;
}
blockquote {
    margin: 0 0 16px 0;
    padding: 0 1em;
    color: #6a737d;
    border-left: 0.25em solid #dfe2e5;
}
blockquote > :first-child { margin-top: 0; }
blockquote > :last-child { margin-bottom: 0; }
table {
    border-spacing: 0;
    border-collapse: collapse;
    display: block;
    width: 100%;
    overflow: auto;
    margin-top: 0;
    margin-bottom: 16px;
}
table th { font-weight: 600; }
table th, table td {
    padding: 6px 13px;
    border: 1px solid #dfe2e5;
}
table tr { background-color: #fff; border-top: 1px solid #c6cbd1; }
table tr:nth-child(2n) { background-color: #f6f8fa; }
img { max-width: 100%; height: auto; box-sizing: content-box; }
hr {
    height: 0.25em;
    padding: 0;
    margin: 24px 0;
    background-color: #e1e4e8;
    border: 0;
}
ul, ol { padding-left: 2em; margin-top: 0; margin-bottom: 16px; }
li { margin-top: 0.25em; }
li + li { margin-top: 0.25em; }
dl dt { font-weight: 600; margin-top: 16px; }
dl dd { margin: 0 0 16px 16px; }
"""

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

_MD_EXTENSIONS = [
    "markdown.extensions.tables",
    "markdown.extensions.fenced_code",
    "markdown.extensions.toc",
    "markdown.extensions.nl2br",
    "markdown.extensions.attr_list",
    "markdown.extensions.def_list",
    "markdown.extensions.footnotes",
]


def convert_md_to_html(file_path: str | Path) -> str:
    """Convert a Markdown file to a complete HTML document string."""
    path = Path(file_path)
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="latin-1")

    md = markdown.Markdown(extensions=_MD_EXTENSIONS)
    body = md.convert(content)
    return _HTML_TEMPLATE.format(css=_GITHUB_CSS, body=body)


def convert_md_string_to_html(md_content: str) -> str:
    """Convert a Markdown string to a complete HTML document string."""
    md = markdown.Markdown(extensions=_MD_EXTENSIONS)
    body = md.convert(md_content)
    return _HTML_TEMPLATE.format(css=_GITHUB_CSS, body=body)
