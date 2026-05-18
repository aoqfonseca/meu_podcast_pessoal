"""Load articles from the JSON files produced by the leitor_links Rust CLI."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel


class Article(BaseModel):
    source: str
    tags: list[str]
    source_url: str
    title: str | None
    link: str | None
    published: datetime | None
    text: str

    @property
    def best_text(self) -> str:
        return self.text


def _pick_text(item: dict) -> str | None:
    for key in ("full_text", "feed_content", "summary"):
        v = item.get(key)
        if v and isinstance(v, str) and v.strip():
            return v.strip()
    return None


def load_day(folder: Path) -> list[Article]:
    """Load every *.json in a day folder, returning normalized Article rows."""
    if not folder.is_dir():
        raise FileNotFoundError(f"input folder does not exist: {folder}")

    articles: list[Article] = []
    for path in sorted(folder.glob("*.json")):
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        source = data.get("fonte", path.stem)
        tags = data.get("tags", [])
        source_url = data.get("url", "")
        for item in data.get("items", []):
            text = _pick_text(item)
            if not text:
                continue
            published_raw = item.get("published")
            published = (
                datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
                if published_raw
                else None
            )
            articles.append(
                Article(
                    source=source,
                    tags=tags,
                    source_url=source_url,
                    title=item.get("title"),
                    link=item.get("link"),
                    published=published,
                    text=text,
                )
            )
    return articles


def resolve_input_folder(input_root: Path, day: date | None) -> Path:
    """Resolve the YYYY-MM-DD folder under input_root. If day is None, use the most recent."""
    if day is not None:
        return input_root / day.isoformat()
    if not input_root.is_dir():
        raise FileNotFoundError(f"input root does not exist: {input_root}")
    iso_dirs: list[Path] = []
    for p in input_root.iterdir():
        if not p.is_dir():
            continue
        try:
            date.fromisoformat(p.name)
        except ValueError:
            continue
        iso_dirs.append(p)
    if not iso_dirs:
        raise FileNotFoundError(f"no YYYY-MM-DD day folders found under {input_root}")
    iso_dirs.sort(key=lambda p: p.name, reverse=True)
    return iso_dirs[0]


def iter_days(input_root: Path) -> Iterable[date]:
    if not input_root.is_dir():
        return []
    out = []
    for p in input_root.iterdir():
        if not p.is_dir():
            continue
        try:
            out.append(date.fromisoformat(p.name))
        except ValueError:
            continue
    return sorted(out)
