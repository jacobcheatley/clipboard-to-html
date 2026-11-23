# clipboard-to-html

Converts plain text in the clipboard to HTML, so it pastes as formatted text into
Teams, Outlook, Google Docs and similar apps. Built for terminal output (box-drawing
tables from Claude Code, hard-wrapped paragraphs and lists), with optional markdown.

Linux on Wayland only (uses `wl-paste` / `wl-copy`). Needs [uv](https://docs.astral.sh/uv/).

## What it converts

Always:

- Box-drawing tables (`┌ │ ├ └`), with cells the renderer wrapped across lines rejoined
- Markdown pipe tables
- Bullet (`-`, `*`, `+`, `•`) and numbered lists, nested by indentation
- Hard-wrapped paragraphs, unwrapped

With `--markdown`: headings, `**bold**`, `*italic*`, `` `code` ``, `~~strike~~`,
`[links](url)`, fenced code blocks and horizontal rules.

Copying from a terminal gives plain text only, so formatting Claude Code renders
(bold, code) cannot be recovered. Ask for raw markdown output and use `--markdown`.

## Usage

```sh
clip2html              # clipboard text -> clipboard HTML
clip2html --markdown   # also convert markdown
clip2html --print      # print the HTML instead
```

After conversion the clipboard holds `text/html` only.

## Install

```sh
ln -s "$PWD/clip2html.py" ~/.local/bin/clip2html
```

GNOME shortcuts (Settings > Keyboard > Custom Shortcuts), or with `gsettings`:

| Shortcut         | Command                 |
| ---------------- | ----------------------- |
| `Super+Shift+V`  | `clip2html`             |
| `Super+Shift+M`  | `clip2html --markdown`  |

Use the absolute path to the symlink in the shortcut command, since GNOME does not
read your shell `PATH`.

## Tests

```sh
uvx pytest
```
