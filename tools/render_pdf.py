#!/usr/bin/env python3
"""Render a system-design study-guide PDF from a Python source module.

Usage:
    python3 render_pdf.py sources/02_url_shortener.py /path/to/output.pdf

The source module must define a top-level `DOC` dict with keys:
    category    str   e.g. "SYSTEM DESIGN INTERVIEW"
    title       str   e.g. "Design a URL Shortener"
    subtitle    str   one-line tagline shown under the title
    read_time   str   e.g. "~ 40 minute read"
    short_title str   used in the page footer
    sections    list  each entry: {num, title, subtitle, blocks}

Each block in `blocks` is a dict with one of these `type` values:
    para            text (HTML inline allowed)
    lead            opening paragraph (slightly larger)
    bullets         items: list[str]  (str may contain HTML)
    numbered        items: list[str]
    h3              text   sub-heading inside a section
    table           headers: list[str]; rows: list[list[str]]
    code            text (rendered in a dark navy code block)
    callout         kind: "insight" | "tip" | "warn" | "key"; title; body
    diagram         dot: graphviz source string; caption: optional
    spacer          (vertical gap)
"""

from __future__ import annotations

import argparse
import html
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

from weasyprint import CSS, HTML

# --------------------------------------------------------------------------
# CSS — matches the existing PDF visual identity (navy banner header, blue
# tables, dark-navy callout/code blocks, light-blue footer).
# --------------------------------------------------------------------------

CSS_TEXT = r"""
@page {
    size: Letter;
    margin: 0.75in 0.75in 1.0in 0.75in;
    @bottom-left {
        content: var(--footer-left);
        font-family: "Helvetica", "Arial", sans-serif;
        font-size: 8.5pt;
        color: #6c8cc7;
        padding-bottom: 0.25in;
    }
    @bottom-right {
        content: "© Study Guide — For personal use only";
        font-family: "Helvetica", "Arial", sans-serif;
        font-size: 8.5pt;
        color: #6c8cc7;
        padding-bottom: 0.25in;
    }
}

@page :first {
    @bottom-left { content: ""; }
    @bottom-right { content: ""; }
}

html { font-family: "Helvetica", "Arial", sans-serif; color: #1a2540; font-size: 10.5pt; line-height: 1.45; }
body { margin: 0; padding: 0; }
* { box-sizing: border-box; }

/* ------- Cover page ------- */
.cover { page: cover; page-break-after: always; padding-top: 0.6in; }
.cover-banner {
    background: #1d2a4d;
    color: #ffffff;
    padding: 36pt 32pt 36pt 32pt;
    border-radius: 4pt;
}
.cover-category {
    font-size: 11pt;
    letter-spacing: 0.18em;
    color: #aebbe0;
    font-weight: 600;
    margin-bottom: 14pt;
}
.cover-title { font-size: 36pt; font-weight: 800; line-height: 1.1; margin: 0 0 8pt 0; }
.cover-subtitle { font-size: 11.5pt; color: #d4ddef; margin: 0 0 28pt 0; }
.cover-meta { font-size: 9.5pt; color: #aebbe0; line-height: 1.6; }

.toc { margin-top: 32pt; padding: 0 4pt; }
.toc-heading {
    font-size: 14pt; font-weight: 700; color: #1d2a4d;
    border-bottom: 1pt solid #c4cee2; padding-bottom: 6pt; margin-bottom: 14pt;
}
.toc-list { list-style: none; padding: 0; margin: 0; }
.toc-list li { font-size: 10.5pt; color: #1a2540; padding: 4pt 0; }
.toc-list .num { color: #2e57b8; font-weight: 700; margin-right: 8pt; }
.toc-list .dot { color: #2e57b8; margin-right: 6pt; }

/* ------- Section banner ------- */
.section { page-break-before: always; }
.section-banner {
    background: #1d2a4d;
    color: #ffffff;
    border-radius: 3pt;
    padding: 14pt 18pt 14pt 18pt;
    display: flex;
    align-items: center;
    margin-bottom: 16pt;
}
.section-num { font-size: 24pt; font-weight: 800; color: #ffffff; min-width: 56pt; }
.section-titles .title { font-size: 16pt; font-weight: 700; color: #ffffff; line-height: 1.1; }
.section-titles .subtitle { font-size: 10pt; color: #aebbe0; margin-top: 2pt; }

h3.block-h3 {
    font-size: 12pt; color: #2e57b8; font-weight: 700;
    border-bottom: 1pt solid #c4cee2; padding-bottom: 4pt;
    margin: 14pt 0 8pt 0;
}

p.lead { font-size: 11pt; color: #1a2540; }
p { margin: 0 0 8pt 0; }
ul, ol { margin: 0 0 10pt 18pt; padding: 0; }
li { margin-bottom: 3pt; }
strong { color: #1a2540; }
em { color: #1a2540; }

/* ------- Tables ------- */
table.tbl { width: 100%; border-collapse: collapse; margin: 6pt 0 12pt 0; font-size: 9.5pt; }
table.tbl thead th {
    background: #2e57b8; color: #ffffff; font-weight: 700;
    text-align: left; padding: 7pt 9pt; border: 1pt solid #2e57b8;
}
table.tbl tbody td {
    background: #ffffff; padding: 6pt 9pt; border: 1pt solid #d4ddef;
    color: #1a2540; vertical-align: top;
}
table.tbl tbody tr:nth-child(even) td { background: #f4f7fc; }

/* ------- Code & callouts (dark navy block) ------- */
.codeblock {
    background: #1d2a4d; color: #d4ddef;
    border-radius: 3pt; padding: 10pt 12pt;
    font-family: "Menlo", "Consolas", "Courier New", monospace;
    font-size: 8.8pt; line-height: 1.5;
    margin: 6pt 0 12pt 0; white-space: pre-wrap;
}

.callout {
    border-left: 4pt solid #2e57b8;
    background: #f4f7fc;
    padding: 9pt 12pt; margin: 8pt 0 12pt 0;
    font-size: 10pt; border-radius: 2pt;
}
.callout.insight { border-color: #2e57b8; }
.callout.tip     { border-color: #2aa775; background: #f0faf5; }
.callout.warn    { border-color: #c45a3b; background: #fbf3f0; }
.callout.key     { border-color: #b8862e; background: #fbf7ee; }
.callout-label {
    font-size: 8.5pt; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; margin-bottom: 4pt;
}
.callout.insight .callout-label { color: #2e57b8; }
.callout.tip     .callout-label { color: #1f8359; }
.callout.warn    .callout-label { color: #963f23; }
.callout.key     .callout-label { color: #886118; }
.callout-title { font-weight: 700; margin-bottom: 3pt; }

/* ------- Diagrams ------- */
.diagram { margin: 8pt 0 12pt 0; text-align: center; }
.diagram svg { max-width: 100%; height: auto; }
.diagram-caption {
    font-size: 9pt; color: #586278; font-style: italic;
    margin-top: 4pt; text-align: center;
}

.spacer { height: 12pt; }
"""

# --------------------------------------------------------------------------
# HTML rendering helpers
# --------------------------------------------------------------------------


def render_block(block: dict[str, Any]) -> str:
    t = block["type"]
    if t == "para":
        return f"<p>{block['text']}</p>"
    if t == "lead":
        return f"<p class='lead'>{block['text']}</p>"
    if t == "bullets":
        items = "".join(f"<li>{i}</li>" for i in block["items"])
        return f"<ul>{items}</ul>"
    if t == "numbered":
        items = "".join(f"<li>{i}</li>" for i in block["items"])
        return f"<ol>{items}</ol>"
    if t == "h3":
        return f"<h3 class='block-h3'>{html.escape(block['text'])}</h3>"
    if t == "table":
        head = "".join(f"<th>{h}</th>" for h in block["headers"])
        body = "".join(
            "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
            for row in block["rows"]
        )
        return f"<table class='tbl'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    if t == "code":
        return f"<pre class='codeblock'>{html.escape(block['text'])}</pre>"
    if t == "callout":
        kind = block.get("kind", "insight")
        label = {
            "insight": "INSIGHT",
            "tip": "TIP",
            "warn": "WARNING",
            "key": "KEY",
        }[kind]
        title = block.get("title", "")
        title_html = f"<div class='callout-title'>{title}</div>" if title else ""
        return (
            f"<div class='callout {kind}'>"
            f"<div class='callout-label'>{label}</div>"
            f"{title_html}"
            f"<div>{block['body']}</div></div>"
        )
    if t == "diagram":
        svg = render_dot_to_svg(block["dot"])
        cap = block.get("caption", "")
        cap_html = f"<div class='diagram-caption'>{html.escape(cap)}</div>" if cap else ""
        return f"<div class='diagram'>{svg}{cap_html}</div>"
    if t == "spacer":
        return "<div class='spacer'></div>"
    raise ValueError(f"unknown block type: {t!r}")


def render_dot_to_svg(dot_src: str) -> str:
    proc = subprocess.run(
        ["dot", "-Tsvg"],
        input=dot_src.encode(),
        capture_output=True,
        check=True,
    )
    svg = proc.stdout.decode()
    # Strip XML preamble so it embeds cleanly inside HTML.
    if svg.startswith("<?xml"):
        svg = svg.split("?>", 1)[1].lstrip()
    if svg.startswith("<!DOCTYPE"):
        svg = svg.split(">", 1)[1].lstrip()
    return svg


def render_section(sec: dict[str, Any]) -> str:
    blocks_html = "".join(render_block(b) for b in sec["blocks"])
    return (
        f"<div class='section'>"
        f"<div class='section-banner'>"
        f"<div class='section-num'>{sec['num']}</div>"
        f"<div class='section-titles'>"
        f"<div class='title'>{html.escape(sec['title'])}</div>"
        f"<div class='subtitle'>{html.escape(sec.get('subtitle', ''))}</div>"
        f"</div></div>"
        f"{blocks_html}"
        f"</div>"
    )


def render_cover(doc: dict[str, Any]) -> str:
    toc_items = "".join(
        f"<li><span class='num'>{s['num']}</span><span class='dot'>·</span>"
        f"{html.escape(s['title'])}</li>"
        for s in doc["sections"]
    )
    return (
        f"<div class='cover'>"
        f"<div class='cover-banner'>"
        f"<div class='cover-category'>{html.escape(doc['category'])}</div>"
        f"<h1 class='cover-title'>{html.escape(doc['title'])}</h1>"
        f"<div class='cover-subtitle'>{html.escape(doc['subtitle'])}</div>"
        f"<div class='cover-meta'>{html.escape(doc['read_time'])}<br>"
        f"© Study Guide — For personal use only</div>"
        f"</div>"
        f"<div class='toc'>"
        f"<div class='toc-heading'>What's Inside</div>"
        f"<ul class='toc-list'>{toc_items}</ul>"
        f"</div></div>"
    )


def render_document(doc: dict[str, Any]) -> str:
    sections_html = "".join(render_section(s) for s in doc["sections"])
    cover_html = render_cover(doc)
    footer_left = f"{doc['category']} · {doc['short_title']} · Interview Study Guide"
    return (
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<style>:root {{ --footer-left: \"{footer_left}\"; }}</style>"
        f"</head><body>{cover_html}{sections_html}</body></html>"
    )


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def load_doc_module(path: Path) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("doc_source", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.DOC


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("source", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()

    doc = load_doc_module(args.source)
    html_text = render_document(doc)
    HTML(string=html_text).write_pdf(
        target=str(args.output),
        stylesheets=[CSS(string=CSS_TEXT)],
    )
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
