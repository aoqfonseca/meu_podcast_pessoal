from __future__ import annotations

from podcast_processor.render import render_report


def test_render_report_has_all_sections():
    md = render_report(
        day_iso="2026-05-18",
        hot_topics_md="- topic 1\n- topic 2",
        summaries=[("Title A", "body a"), ("Title B", "body b")],
        reading_table_md="| # | Título |\n|---|---|\n| 1 | x |",
        audio_relpath="podcast.wav",
    )
    assert "# Podcast diário — 2026-05-18" in md
    assert "## 🔥 Tópicos quentes" in md
    assert "## 📚 Lista de leitura" in md
    assert "## 📝 Resumos dos artigos" in md
    assert "### Title A" in md
    assert "### Title B" in md
    assert "## 🎧 Podcast" in md
    assert "[Ouvir](podcast.wav)" in md


def test_render_report_omits_audio_section_when_no_audio():
    md = render_report(
        day_iso="2026-05-18",
        hot_topics_md="x",
        summaries=[],
        reading_table_md="t",
        audio_relpath=None,
    )
    assert "## 🎧 Podcast" not in md
