"""Build the static blog site from generated daily outputs."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import config

SITE_SRC = config.PROJECT_ROOT / "site_src"
SITE_DOCS = SITE_SRC / "docs"
POSTS_DIR = SITE_DOCS / "blog" / "posts"
AUDIO_DIR = SITE_DOCS / "audio"
SITE_BUILD = config.PROJECT_ROOT / "site"

DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class DayOutput:
    day: date
    folder: Path
    report_md: Path
    audio_mp3: Path | None


def discover_days(output_root: Path) -> list[DayOutput]:
    days: list[DayOutput] = []
    if not output_root.exists():
        return days
    for child in sorted(output_root.iterdir()):
        if not child.is_dir() or not DAY_RE.match(child.name):
            continue
        report = child / "report.md"
        if not report.exists():
            continue
        mp3 = child / "podcast.mp3"
        days.append(
            DayOutput(
                day=date.fromisoformat(child.name),
                folder=child,
                report_md=report,
                audio_mp3=mp3 if mp3.exists() else None,
            )
        )
    return days


def _strip_first_heading(md: str) -> tuple[str, str]:
    """Return (title, body_without_first_h1_and_generated_line)."""
    lines = md.splitlines()
    title = ""
    body_start = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            body_start = i + 1
            break
    # Skip the "_Gerado em ..._" line if present right after the title.
    while body_start < len(lines) and (
        lines[body_start].strip() == "" or lines[body_start].startswith("_Gerado em")
    ):
        body_start += 1
    return title, "\n".join(lines[body_start:])


def _replace_audio_block(
    body: str, audio_src_path: str | None, audio_link_path: str | None
) -> str:
    """Replace the trailing '## 🎧 Podcast' section with an HTML <audio> player.

    `audio_src_path` is used in the raw HTML <audio src> and must be relative to
    the *rendered post URL* (mkdocs does not rewrite raw HTML paths).
    `audio_link_path` is used in the markdown download link and must be relative
    to the *source markdown file* (mkdocs rewrites markdown links).
    """
    if audio_src_path is None or audio_link_path is None:
        return re.sub(r"##\s+🎧\s+Podcast.*\Z", "", body, flags=re.DOTALL).rstrip() + "\n"

    player = (
        "## 🎧 Podcast\n\n"
        f'<audio controls preload="none" src="{audio_src_path}"></audio>\n\n'
        f"[Baixar MP3]({audio_link_path})\n"
    )
    if "## 🎧 Podcast" in body:
        return re.sub(r"##\s+🎧\s+Podcast.*\Z", player, body, flags=re.DOTALL)
    return body.rstrip() + "\n\n" + player


def render_post(
    day: DayOutput,
    audio_src_path: str | None,
    audio_link_path: str | None,
) -> tuple[str, str]:
    """Return (post_filename, post_markdown_with_frontmatter)."""
    raw = day.report_md.read_text(encoding="utf-8")
    title, body = _strip_first_heading(raw)
    if not title:
        title = f"Episódio {day.day.isoformat()}"

    body = _replace_audio_block(body, audio_src_path, audio_link_path)

    front_matter_lines = [
        "---",
        f"date: {day.day.isoformat()}",
        f'title: "{title}"',
    ]
    if audio_link_path:
        front_matter_lines.append(f"description: Episódio com áudio em {audio_link_path}")
    front_matter_lines.append("---")
    front_matter = "\n".join(front_matter_lines)

    post = f"{front_matter}\n\n# {title}\n\n{body.strip()}\n"
    filename = f"{day.day.isoformat()}.md"
    return filename, post


def sync(output_root: Path | None = None, copy_audio: bool = True) -> list[Path]:
    """Generate one blog post per day output. Returns the list of written post files."""
    out_root = output_root or config.DEFAULT_OUTPUT_ROOT
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for day in discover_days(out_root):
        audio_src: str | None = None
        audio_link: str | None = None
        if day.audio_mp3 is not None:
            audio_name = f"{day.day.isoformat()}.mp3"
            if copy_audio:
                shutil.copy2(day.audio_mp3, AUDIO_DIR / audio_name)
            # Raw HTML <audio src> is NOT rewritten by mkdocs — must be relative
            # to the rendered post URL (/blog/yyyy/MM/dd/<slug>/ = 5 levels deep).
            audio_src = f"../../../../../audio/{audio_name}"
            # Markdown links ARE rewritten — use source-relative path
            # (from docs/blog/posts/ to docs/audio/).
            audio_link = f"../../audio/{audio_name}"

        filename, post_md = render_post(day, audio_src, audio_link)
        target = POSTS_DIR / filename
        target.write_text(post_md, encoding="utf-8")
        written.append(target)
    return written


def build(strict: bool = False) -> Path:
    """Run `mkdocs build` against site_src and return the build dir."""
    cmd = ["mkdocs", "build", "-f", str(SITE_SRC / "mkdocs.yml"), "-d", str(SITE_BUILD)]
    if strict:
        cmd.append("--strict")
    subprocess.run(cmd, check=True)
    return SITE_BUILD
