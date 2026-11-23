#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Convert plain-text tables and lists in the clipboard to HTML, for pasting
formatted text into Teams, Outlook, Google Docs and similar apps."""

import argparse
import html
import re
import subprocess
import sys

LIST_ITEM = re.compile(r"^(\s*)([-*+•]|(\d+)[.)])\s+(.*)$")
PIPE_ROW = re.compile(r"^\s*\|.*\|\s*$")
PIPE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
RULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
CLAUDE_BULLET = re.compile(r"^\s*● ")

TABLE_STYLE = 'style="border-collapse:collapse"'
CELL_STYLE = 'style="border:1px solid #999;padding:4px 8px;vertical-align:top;text-align:left"'


def inline(text: str, markdown: bool) -> str:
    escaped = html.escape(text.strip())
    if not markdown:
        return escaped
    code_spans: list[str] = []

    def stash_code(match: re.Match) -> str:
        code_spans.append(match[1])
        return f"\x00{len(code_spans) - 1}\x00"

    escaped = re.sub(r"`([^`]+)`", stash_code, escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: f"<b>{m[1] or m[2]}</b>", escaped)
    escaped = re.sub(
        r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])|(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)",
        lambda m: f"<i>{m[1] or m[2]}</i>",
        escaped,
    )
    escaped = re.sub(r"~~(.+?)~~", r"<s>\1</s>", escaped)
    escaped = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', escaped)
    return re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{code_spans[int(m[1])]}</code>", escaped)


def render_table(rows: list[list[str]], markdown: bool) -> str:
    def row_html(cells: list[str], tag: str) -> str:
        return "<tr>" + "".join(f"<{tag} {CELL_STYLE}>{inline(c, markdown)}</{tag}>" for c in cells) + "</tr>"

    header, *body = rows
    return (
        f"<table {TABLE_STYLE}><thead>{row_html(header, 'th')}</thead>"
        f"<tbody>{''.join(row_html(r, 'td') for r in body)}</tbody></table>"
    )


def parse_box_table(lines: list[str]) -> list[list[str]]:
    """Rows sit between the box-drawing separator lines; a row spanning several
    lines is a cell wrapped by the renderer, so its fragments join with spaces."""
    rows: list[list[str]] = []
    fragments: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("│"):
            fragments.append([c.strip() for c in stripped.strip("│").split("│")])
        elif fragments:
            rows.append([" ".join(f for f in column if f) for column in zip(*fragments)])
            fragments = []
    return rows


def split_pipe_row(line: str) -> list[str]:
    cells = re.split(r"(?<!\\)\|", line.strip().strip("|"))
    return [c.replace("\\|", "|").strip() for c in cells]


def render_list(items: list[tuple[int, str, int, str]]) -> str:
    out: list[str] = []
    open_lists: list[tuple[int, str]] = []
    for indent, tag, start, text in items:
        while open_lists and open_lists[-1][0] > indent:
            out.append(f"</li></{open_lists.pop()[1]}>")
        if open_lists and open_lists[-1] == (indent, tag):
            out.append("</li>")
        else:
            if open_lists and open_lists[-1][0] == indent:
                out.append(f"</li></{open_lists.pop()[1]}>")
            out.append(f'<ol start="{start}">' if tag == "ol" and start != 1 else f"<{tag}>")
            open_lists.append((indent, tag))
        out.append(f"<li>{text}")
    out.extend(f"</li></{tag}>" for _, tag in reversed(open_lists))
    return "".join(out)


def dedent(lines: list[str]) -> list[str]:
    """Strip the common indent of a terminal selection. The first line is
    checked separately because a selection often starts mid-line."""
    if lines:
        lines[0] = CLAUDE_BULLET.sub("", lines[0])
    indents = [len(l) - len(l.lstrip()) for l in lines[1:] if l.strip()]
    common = min(indents, default=0)
    first = lines[:1]
    if first and len(first[0]) - len(first[0].lstrip()) < common:
        first = [first[0].lstrip()]
    else:
        first = [l[common:] for l in first]
    return first + [l[common:] for l in lines[1:]]


def convert(text: str, markdown: bool = False) -> str:
    lines = dedent(text.expandtabs().splitlines())
    blocks: list[str] = []
    paragraph: list[str] = []
    list_items: list[tuple[int, str, int, str]] = []
    raw_item: list[str] = []

    def finish_item() -> None:
        if raw_item:
            indent, tag, start, _ = list_items[-1]
            list_items[-1] = (indent, tag, start, inline(" ".join(raw_item), markdown))
            raw_item.clear()

    def flush() -> None:
        finish_item()
        if list_items:
            blocks.append(render_list(list_items))
            list_items.clear()
        if paragraph:
            blocks.append(f"<p>{inline(' '.join(paragraph), markdown)}</p>")
            paragraph.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("┌"):
            flush()
            end = i
            while end < len(lines) and not lines[end].strip().startswith("└"):
                end += 1
            rows = parse_box_table(lines[i : end + 1])
            if rows:
                blocks.append(render_table(rows, markdown))
            i = end + 1
            continue

        if PIPE_ROW.match(line) and i + 1 < len(lines) and PIPE_SEPARATOR.match(lines[i + 1]):
            flush()
            rows = [split_pipe_row(line)]
            i += 2
            while i < len(lines) and PIPE_ROW.match(lines[i]):
                rows.append(split_pipe_row(lines[i]))
                i += 1
            blocks.append(render_table(rows, markdown))
            continue

        if markdown and FENCE.match(line):
            flush()
            fence = FENCE.match(line)[1]
            end = i + 1
            while end < len(lines) and not lines[end].strip().startswith(fence):
                end += 1
            code = "\n".join(lines[i + 1 : end])
            blocks.append(f"<pre><code>{html.escape(code)}</code></pre>")
            i = end + 1
            continue

        if not stripped:
            flush()
        elif markdown and (heading := HEADING.match(stripped)):
            flush()
            level = len(heading[1])
            blocks.append(f"<h{level}>{inline(heading[2], markdown)}</h{level}>")
        elif markdown and RULE.match(line):
            flush()
            blocks.append("<hr>")
        elif item := LIST_ITEM.match(line):
            if paragraph:
                flush()
            finish_item()
            tag = "ol" if item[3] else "ul"
            list_items.append((len(item[1]), tag, int(item[3] or 1), ""))
            raw_item.append(item[4])
        elif list_items:
            raw_item.append(stripped)
        else:
            paragraph.append(stripped)
        i += 1

    flush()
    return '<meta charset="utf-8">' + "\n".join(blocks)


def notify_failure(message: str) -> None:
    subprocess.run(["notify-send", "--app-name=clip2html", "clip2html failed", message], check=False)
    print(message, file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-m", "--markdown", action="store_true", help="also convert markdown: headings, bold, italic, code, links, fences")
    parser.add_argument("-p", "--print", action="store_true", help="print the HTML instead of copying it to the clipboard")
    args = parser.parse_args()

    try:
        text = subprocess.run(
            ["wl-paste", "--no-newline", "--type", "text/plain"], capture_output=True, text=True, check=True
        ).stdout
    except subprocess.CalledProcessError as error:
        notify_failure(f"Could not read plain text from the clipboard: {error.stderr.strip()}")
        return 1

    converted = convert(text, markdown=args.markdown)
    if args.print:
        print(converted)
        return 0
    subprocess.run(["wl-copy", "--type", "text/html"], input=converted, text=True, check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
