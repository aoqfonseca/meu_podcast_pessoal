from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from podcast_processor import loader


def _write_source(folder: Path, name: str, payload: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def day_folder(tmp_path: Path) -> Path:
    d = tmp_path / "2026-05-18"
    _write_source(
        d,
        "good",
        {
            "fonte": "Sample Feed",
            "tags": ["Tech"],
            "url": "http://example.com/feed",
            "items": [
                {
                    "title": "First post",
                    "link": "http://example.com/1",
                    "published": "2026-05-18T10:00:00+00:00",
                    "summary": "short summary",
                    "feed_content": "feed content",
                    "full_text": "full body text",
                    "scrape_error": None,
                }
            ],
        },
    )
    _write_source(
        d,
        "fallback",
        {
            "fonte": "No FullText",
            "tags": ["IA"],
            "url": "http://example.com/feed2",
            "items": [
                {
                    "title": "fallback item",
                    "link": "http://example.com/2",
                    "published": None,
                    "summary": "fallback summary",
                    "feed_content": None,
                    "full_text": None,
                    "scrape_error": "404",
                }
            ],
        },
    )
    _write_source(
        d,
        "empty",
        {
            "fonte": "Empty",
            "tags": [],
            "url": "http://example.com/feed3",
            "items": [
                {
                    "title": "no text at all",
                    "link": "http://example.com/3",
                    "published": None,
                    "summary": None,
                    "feed_content": None,
                    "full_text": None,
                    "scrape_error": "x",
                }
            ],
        },
    )
    return d


def test_load_day_picks_full_text_first(day_folder: Path):
    arts = loader.load_day(day_folder)
    by_source = {a.source: a for a in arts}
    assert by_source["Sample Feed"].text == "full body text"


def test_load_day_falls_back_to_summary(day_folder: Path):
    arts = loader.load_day(day_folder)
    by_source = {a.source: a for a in arts}
    assert by_source["No FullText"].text == "fallback summary"


def test_load_day_skips_items_with_no_usable_text(day_folder: Path):
    arts = loader.load_day(day_folder)
    sources = {a.source for a in arts}
    assert "Empty" not in sources


def test_load_day_parses_published_iso(day_folder: Path):
    arts = loader.load_day(day_folder)
    sample = next(a for a in arts if a.source == "Sample Feed")
    assert sample.published is not None
    assert sample.published.year == 2026


def test_load_day_handles_missing_folder(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        loader.load_day(tmp_path / "does-not-exist")


def test_resolve_input_folder_specific_date(tmp_path: Path):
    (tmp_path / "2026-05-18").mkdir()
    out = loader.resolve_input_folder(tmp_path, date(2026, 5, 18))
    assert out.name == "2026-05-18"


def test_resolve_input_folder_latest(tmp_path: Path):
    (tmp_path / "2026-05-17").mkdir()
    (tmp_path / "2026-05-18").mkdir()
    (tmp_path / "not-a-date").mkdir()
    out = loader.resolve_input_folder(tmp_path, None)
    assert out.name == "2026-05-18"


def test_iter_days_returns_only_valid_iso_dirs(tmp_path: Path):
    (tmp_path / "2026-05-18").mkdir()
    (tmp_path / "2026-05-19").mkdir()
    (tmp_path / "scratch").mkdir()
    (tmp_path / "file.txt").write_text("x")
    days = list(loader.iter_days(tmp_path))
    assert [d.isoformat() for d in days] == ["2026-05-18", "2026-05-19"]
