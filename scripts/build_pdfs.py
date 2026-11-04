#!/usr/bin/env python3
"""Build the light and dark PDFs of the lab guide.

Renders the Markdown with GitHub-style heading anchors, then prints it with
headless Chrome or Chromium. Needs the docs packages from requirements-dev.txt
(run `make venv`) and a Chromium-based browser. Set CHROME to pick one.

    .venv/bin/python scripts/build_pdfs.py            # or: make pdf
"""

from __future__ import annotations

import argparse
import glob
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from markdown_it import MarkdownIt
from mdit_py_plugins.tasklists import tasklists_plugin

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GUIDE = ROOT / "docs" / "spaces-lab-guide-v1.md"
TITLE = "Spaces Mockup MCP Lab Guide"

BASE_CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm;
  @bottom-center { content: "TITLE · page " counter(page) " of " counter(pages);
    font: 8px sans-serif; color: #666; } }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: -apple-system, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
  font-size: 10.5pt; line-height: 1.5; color: #1f2328; background: #fff; margin: 0; }
h1 { font-size: 22pt; margin: 0 0 4pt; border-bottom: 1px solid #d1d9e0; padding-bottom: 6pt; }
h2 { font-size: 16pt; margin: 18pt 0 8pt; border-bottom: 1px solid #d1d9e0;
  padding-bottom: 4pt; }
h3 { font-size: 12.5pt; margin: 14pt 0 6pt; }
h4 { font-size: 11pt; margin: 12pt 0 4pt; }
h1, h2, h3, h4 { break-after: avoid; }
p, li { orphans: 3; widows: 3; }
a { color: #0969da; text-decoration: none; }
code { font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, "DejaVu Sans Mono",
  monospace; font-size: 9pt; background: #eff1f3; padding: 1pt 3pt; border-radius: 3pt; }
pre { background: #f6f8fa; border: 1px solid #d1d9e0; border-radius: 4pt; padding: 8pt 10pt;
  white-space: pre-wrap; word-break: break-word; break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 10.5pt; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 9pt; }
th, td { border: 1px solid #d1d9e0; padding: 4pt 6pt; text-align: left; vertical-align: top; }
th { background: #f6f8fa; }
tr { break-inside: avoid; }
h4 + table { break-inside: avoid; }
td code { word-break: break-word; }
blockquote { margin: 12pt 0; padding: 8pt 14pt; border-left: 5pt solid #0969da;
  background: #ddf4ff; border-radius: 3pt; break-inside: avoid; }
blockquote h2 { border: none; margin: 0 0 4pt; color: #0550ae; }
.contains-task-list, .task-list-item { list-style: none; }
.task-list-item input { margin-right: 6pt; }
/* Start setup, each lab after the first, the stretch goals and the answer key on a new page */
h2#mcp-server-setup, h2[id^="lab-"]:not(#lab-1--rooms-and-environment), h2#stretch-goals,
h2#answer-key, blockquote.lab-note { break-before: page; }
h2[id^="lab-"] { margin-top: 0; }
""".replace("TITLE", TITLE)

DARK_CSS = """
@page { background: #0d1117; @bottom-center { color: #9198a1; } }
html, body { background: #0d1117; color: #e6edf3; }
h1, h2 { border-bottom-color: #3d444d; }
a { color: #4493f8; }
code { background: #262c36; color: #e6edf3; }
pre { background: #151b23; border-color: #3d444d; }
pre code { background: none; }
th, td { border-color: #3d444d; }
th { background: #151b23; }
tr:nth-child(2n) td { background: #10151c; }
blockquote { background: #0c2d6b; border-left-color: #4493f8; color: #e6edf3; }
blockquote h2 { color: #79c0ff; }
blockquote a { color: #79c0ff; }
input[type=checkbox] { accent-color: #4493f8; filter: invert(0.85); }
"""


def github_slug(text: str, seen: dict[str, int]) -> str:
    """Heading anchor the way GitHub makes it, so the guide's #links resolve."""
    slug = re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", "-")
    count = seen.get(slug, 0)
    seen[slug] = count + 1
    return slug if count == 0 else f"{slug}-{count}"


def render_body(markdown: str) -> str:
    md = MarkdownIt("commonmark", {"html": False}).enable("table").use(tasklists_plugin)
    tokens = md.parse(markdown)
    seen: dict[str, int] = {}
    for i, token in enumerate(tokens):
        if token.type == "heading_open":
            inline = tokens[i + 1]
            plain = "".join(
                c.content for c in inline.children or [] if c.type in ("text", "code_inline")
            )
            token.attrSet("id", github_slug(plain, seen))
    body = md.renderer.render(tokens, md.options, {})
    # Let long tool names in table cells break only after underscores.
    body = re.sub(
        r"(<td>\s*<code>)([^<]+)(</code>)",
        lambda m: m.group(1) + m.group(2).replace("_", "_<wbr>") + m.group(3),
        body,
    )
    # The "answers are at the back" note starts the Lab 1 page.
    body, found = re.subn(
        r'<blockquote>(\s*<h2 id="answers-are-at-the-back)',
        r'<blockquote class="lab-note">\1',
        body,
    )
    if found != 1:
        raise SystemExit("build_pdfs: 'Answers are at the back' note not found in the guide")
    return body


def page(body: str, dark: bool) -> str:
    css = BASE_CSS + (DARK_CSS if dark else "")
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{html.escape(TITLE)}</title><style>{css}</style></head>"
        f"<body>{body}</body></html>"
    )


def find_chrome() -> str:
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome"):
        if path := shutil.which(name):
            return path
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        *sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium*/chrome-*/chrome*"))),
    ]
    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    raise SystemExit("build_pdfs: no Chrome or Chromium found. Set CHROME=/path/to/chrome.")


def print_pdf(chrome: str, html_path: Path, pdf_path: Path) -> None:
    cmd = [
        chrome,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--generate-pdf-document-outline",
        f"--print-to-pdf={pdf_path}",
        html_path.as_uri(),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0 and "No usable sandbox" in result.stderr:
        # Ubuntu 23.10+ blocks Chrome's sandbox for unprivileged users. Chrome only loads the
        # local HTML this script just wrote (raw HTML in the Markdown is disabled), so retry
        # without it rather than fail.
        print("build_pdfs: Chrome sandbox unavailable here; retrying with --no-sandbox")
        result = subprocess.run(
            [cmd[0], "--no-sandbox", *cmd[1:]], capture_output=True, text=True, timeout=120
        )
    if result.returncode != 0 or not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(f"build_pdfs: Chrome failed to write {pdf_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("guide", nargs="?", type=Path, default=DEFAULT_GUIDE)
    parser.add_argument("--out-dir", type=Path, help="defaults to the guide's folder")
    args = parser.parse_args()
    guide = args.guide.resolve()
    out_dir = (args.out_dir or guide.parent).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    body = render_body(guide.read_text(encoding="utf-8"))
    chrome = find_chrome()
    with tempfile.TemporaryDirectory() as tmp:
        for suffix, dark in (("", False), ("-dark", True)):
            html_path = Path(tmp) / f"guide{suffix}.html"
            html_path.write_text(page(body, dark), encoding="utf-8")
            pdf_path = out_dir / f"{guide.stem}{suffix}.pdf"
            print_pdf(chrome, html_path, pdf_path)
            print(
                "wrote", pdf_path.relative_to(ROOT) if pdf_path.is_relative_to(ROOT) else pdf_path
            )


if __name__ == "__main__":
    main()
