from clip2html import convert

BOX_TABLE = """\
  ┌──────────────┬───────────────────────┐
  │    Server    │        Status         │
  ├──────────────┼───────────────────────┤
  │ alpha, beta, │ Upgraded; both passed │
  │ gamma        │ the health check      │
  ├──────────────┼───────────────────────┤
  │ delta        │ Rolled back <v2>      │
  └──────────────┴───────────────────────┘
"""


def test_box_table_joins_wrapped_cells_and_uses_first_row_as_header():
    out = convert(BOX_TABLE)
    assert out.count("<th ") == 2 and ">Server</th>" in out
    assert ">alpha, beta, gamma</td>" in out
    assert ">Upgraded; both passed the health check</td>" in out
    assert "Rolled back &lt;v2&gt;" in out
    assert out.count("<tr>") == 3


def test_pipe_table():
    out = convert("| a | b |\n|---|:-:|\n| 1 | x \\| y |\n")
    assert ">a</th>" in out and ">1</td>" in out and ">x | y</td>" in out


def test_nested_mixed_lists_with_wrapped_items():
    text = "- one\n  wrapped\n- two\n  1. first\n  2. second\n- three\n"
    assert convert(text) == (
        '<meta charset="utf-8"><ul><li>one wrapped</li><li>two'
        "<ol><li>first</li><li>second</li></ol></li><li>three</li></ul>"
    )


def test_numbered_list_keeps_start_number():
    assert '<ol start="3">' in convert("3. three\n4. four")


def test_paragraphs_unwrap_and_claude_bullet_prefix_is_dropped():
    out = convert("● This is a\n  wrapped line.\n\n  Second para.")
    assert "<p>This is a wrapped line.</p>" in out and "<p>Second para.</p>" in out


def test_markdown_flag_controls_inline_formatting():
    text = "# Title\n**bold** *it* `a*b*c` [link](https://x.y)"
    plain = convert(text)
    assert "<b>" not in plain and "**bold**" in plain
    md = convert(text, markdown=True)
    assert "<h1>Title</h1>" in md
    assert "<b>bold</b>" in md and "<i>it</i>" in md
    assert "<code>a*b*c</code>" in md
    assert '<a href="https://x.y">link</a>' in md


def test_markdown_code_fence_kept_verbatim():
    out = convert("```\n- not a list\n  <tag>\n```", markdown=True)
    assert "<pre><code>- not a list\n  &lt;tag&gt;</code></pre>" in out
