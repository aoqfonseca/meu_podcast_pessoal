from __future__ import annotations

from podcast_processor.loader import Article
from podcast_processor.summarizer import build_reading_table


def _art(title: str | None, link: str | None, source: str = "S", tags=("Tech",)) -> Article:
    return Article(
        source=source,
        tags=list(tags),
        source_url="http://x",
        title=title,
        link=link,
        published=None,
        text="t",
    )


def test_reading_table_headers():
    md = build_reading_table([])
    assert md.splitlines()[:2] == [
        "| # | Título | Fonte | Tags | Link |",
        "|---|---|---|---|---|",
    ]


def test_reading_table_rows_numbered_starting_at_one():
    md = build_reading_table([_art("a", "http://1"), _art("b", "http://2")])
    rows = md.splitlines()[2:]
    assert rows[0].startswith("| 1 |")
    assert rows[1].startswith("| 2 |")


def test_reading_table_escapes_pipe_in_title():
    md = build_reading_table([_art("foo | bar", "http://1")])
    assert "foo \\| bar" in md


def test_reading_table_dash_when_no_link():
    md = build_reading_table([_art("only title", None)])
    assert "| — |" in md


def test_reading_table_link_markdown_when_present():
    md = build_reading_table([_art("x", "http://example.com/article")])
    assert "[abrir](http://example.com/article)" in md
