"""Compose the final markdown report."""

from __future__ import annotations

from datetime import datetime


def render_report(
    day_iso: str,
    hot_topics_md: str,
    summaries: list[tuple[str, str]],  # (title-or-source, body)
    reading_table_md: str,
    audio_relpath: str | None,
) -> str:
    now = datetime.now().isoformat(timespec="seconds")
    parts = [
        f"# Podcast diário — {day_iso}",
        f"_Gerado em {now}_",
        "",
        "## 🔥 Tópicos quentes",
        hot_topics_md,
        "",
        "## 📚 Lista de leitura",
        reading_table_md,
        "",
        "## 📝 Resumos dos artigos",
    ]
    for title, body in summaries:
        parts.append(f"### {title}")
        parts.append(body)
        parts.append("")

    if audio_relpath:
        parts.append("## 🎧 Podcast")
        parts.append(f"[Ouvir]({audio_relpath})")
        parts.append("")

    return "\n".join(parts)
