"""Command-line entrypoint."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from . import config, loader, publish, render, script_writer, summarizer, tts, vectorstore

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


def _parse_day(value: Optional[str]) -> date | None:
    if value is None or value.lower() == "latest":
        return None
    if value.lower() == "today":
        return date.today()
    return date.fromisoformat(value)


@app.command()
def run(
    date_str: Optional[str] = typer.Option(
        None, "--date", help="YYYY-MM-DD, 'today', or 'latest' (default: latest)."
    ),
    input_root: Path = typer.Option(
        config.DEFAULT_INPUT_ROOT, "--input", help="Root with YYYY-MM-DD subfolders."
    ),
    output_root: Path = typer.Option(
        config.DEFAULT_OUTPUT_ROOT, "--output", help="Where to write the report + audio."
    ),
    faiss_dir: Path = typer.Option(
        config.DEFAULT_FAISS_DIR, "--faiss-dir", help="Persistent FAISS index path."
    ),
    cache_dir: Path = typer.Option(
        config.DEFAULT_CACHE_DIR,
        "--cache-dir",
        help="Persistent cache for per-article LLM summaries.",
    ),
    skip_audio: bool = typer.Option(False, "--skip-audio", help="Don't call TTS."),
    skip_vectorize: bool = typer.Option(
        False, "--skip-vectorize", help="Skip FAISS ingestion (still loads index for retrieval)."
    ),
    no_cache: bool = typer.Option(
        False, "--no-cache", help="Disable the per-article summary cache."
    ),
    refresh_cache: bool = typer.Option(
        False, "--refresh-cache", help="Recompute summaries even if cached (overwrites cache)."
    ),
    minutes: int = typer.Option(5, "--minutes", help="Target podcast length in minutes."),
    tts_provider: Optional[str] = typer.Option(
        None,
        "--tts-provider",
        help="TTS backend: 'edge' (free, default) or 'gemini' (paid).",
    ),
) -> None:
    """Build the daily podcast for a given day folder."""
    settings = config.Settings.from_env()
    day = _parse_day(date_str)
    folder = loader.resolve_input_folder(input_root, day)
    day_iso = folder.name
    console.print(f"[bold cyan]→[/bold cyan] processing {folder}")

    articles = loader.load_day(folder)
    if not articles:
        raise typer.BadParameter(f"no usable articles found in {folder}")
    console.print(f"  loaded [bold]{len(articles)}[/bold] articles")

    embeddings = vectorstore.build_embeddings(settings.embedding_model)
    if not skip_vectorize:
        docs = vectorstore.articles_to_documents(
            articles, day_iso, settings.chunk_size, settings.chunk_overlap
        )
        store = vectorstore.ingest(docs, faiss_dir, embeddings)
        console.print(f"  FAISS index now at [bold]{store.index.ntotal}[/bold] vectors")
    else:
        store = vectorstore.load_or_create(faiss_dir, embeddings)
        if store is None:
            console.print("  [yellow]no existing FAISS index — retrieval will be skipped[/yellow]")

    context_excerpts: list[str] = []
    if store is not None:
        try:
            hits = store.similarity_search("temas em destaque, tendências de tecnologia hoje", k=8)
            context_excerpts = [
                f"[{h.metadata.get('source', '?')}] {h.page_content[:400]}" for h in hits
            ]
        except Exception as e:  # noqa: BLE001
            console.print(f"  [yellow]similarity_search failed: {e}[/yellow]")

    chat = summarizer.build_chat(settings.require_google_key(), settings.text_model)

    console.print(f"  generating per-article summaries for [bold]{len(articles)}[/bold] articles…")
    summaries: list[tuple[str, str]] = []
    cache_target: Path | None = None if no_cache else (cache_dir / "summaries")
    hits = 0
    misses = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TextColumn(
            "[green]{task.fields[hits]} cached[/green] / [yellow]{task.fields[misses]} new[/yellow]"
        ),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("ETA"),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("summaries", total=len(articles), hits=0, misses=0)
        for art in articles:
            head = art.title or art.source
            short = (head[:60] + "…") if len(head) > 60 else head
            progress.update(task, description=f"[cyan]{short}")
            body, was_hit = summarizer.cached_summarize_article(
                chat, art, cache_target, refresh=refresh_cache
            )
            if was_hit:
                hits += 1
            else:
                misses += 1
            summaries.append((head, body))
            progress.update(task, advance=1, hits=hits, misses=misses)
    if cache_target is not None:
        console.print(
            f"  cache: [bold green]{hits}[/bold green] hit / "
            f"[bold yellow]{misses}[/bold yellow] new ({cache_target})"
        )

    console.print("  generating hot topics…")
    hot_topics = summarizer.generate_hot_topics(chat, articles, context_excerpts)

    reading_table = summarizer.build_reading_table(articles)

    out_day = output_root / day_iso
    out_day.mkdir(parents=True, exist_ok=True)

    console.print("  generating podcast script…")
    summaries_md = "\n\n".join(f"**{t}**\n\n{b}" for t, b in summaries)
    script_text = script_writer.generate_podcast_script(
        chat, hot_topics, summaries_md, minutes=minutes
    )
    (out_day / "podcast.txt").write_text(script_text, encoding="utf-8")

    audio_relpath: str | None = None
    if not skip_audio:
        provider = (tts_provider or settings.tts_provider).lower()
        if provider == "edge":
            console.print(f"  synthesizing audio via Edge TTS ({settings.edge_tts_voice})…")
            mp3_path = out_day / "podcast.mp3"
            tts.synthesize_edge_to_mp3(settings.edge_tts_voice, script_text, mp3_path)
            audio_relpath = mp3_path.name
            console.print(f"  audio → [bold]{mp3_path}[/bold]")
        elif provider == "gemini":
            console.print(f"  synthesizing audio via Gemini TTS ({settings.tts_voice})…")
            wav_path = out_day / "podcast.wav"
            tts.synthesize_to_wav(
                settings.require_google_key(),
                settings.tts_model,
                settings.tts_voice,
                script_text,
                wav_path,
            )
            audio_relpath = wav_path.name
            console.print(f"  audio → [bold]{wav_path}[/bold]")
        else:
            raise typer.BadParameter(f"unknown tts provider: {provider!r}")

    report_md = render.render_report(
        day_iso=day_iso,
        hot_topics_md=hot_topics,
        summaries=summaries,
        reading_table_md=reading_table,
        audio_relpath=audio_relpath,
    )
    report_path = out_day / "report.md"
    report_path.write_text(report_md, encoding="utf-8")
    console.print(f"[bold green]✓[/bold green] report → {report_path}")


@app.command("list")
def list_days(
    input_root: Path = typer.Option(config.DEFAULT_INPUT_ROOT, "--input"),
) -> None:
    """List available day folders under the input root."""
    days = list(loader.iter_days(input_root))
    if not days:
        console.print(f"[yellow]no day folders under {input_root}[/yellow]")
        return
    for d in days:
        console.print(d.isoformat())


@app.command()
def info() -> None:
    """Show resolved configuration."""
    settings = config.Settings.from_env()
    console.print(f"text_model       = {settings.text_model}")
    console.print(f"tts_provider     = {settings.tts_provider}")
    console.print(f"tts_model        = {settings.tts_model}")
    console.print(f"tts_voice        = {settings.tts_voice}")
    console.print(f"edge_tts_voice   = {settings.edge_tts_voice}")
    console.print(f"embedding_model  = {settings.embedding_model}")
    console.print(f"input default    = {config.DEFAULT_INPUT_ROOT}")
    console.print(f"output default   = {config.DEFAULT_OUTPUT_ROOT}")
    console.print(f"faiss default    = {config.DEFAULT_FAISS_DIR}")
    console.print(f"api key present  = {bool(settings.google_api_key)}")
    console.print(f"now              = {datetime.now().isoformat(timespec='seconds')}")


@app.command("build-site")
def build_site(
    output_root: Path = typer.Option(
        config.DEFAULT_OUTPUT_ROOT, "--output", help="Root with YYYY-MM-DD output folders."
    ),
    build: bool = typer.Option(
        True, "--build/--no-build", help="Run `mkdocs build` after syncing posts."
    ),
    strict: bool = typer.Option(False, "--strict", help="Fail on mkdocs warnings."),
    skip_audio: bool = typer.Option(
        False, "--skip-audio", help="Don't copy MP3 files into the site."
    ),
) -> None:
    """Generate blog posts from data/outputs and (optionally) build the static site."""
    written = publish.sync(output_root, copy_audio=not skip_audio)
    if not written:
        console.print(f"[yellow]no day outputs found under {output_root}[/yellow]")
        return
    console.print(f"  wrote [bold]{len(written)}[/bold] post(s) to {publish.POSTS_DIR}")
    for p in written:
        console.print(f"    • {p.name}")
    if build:
        console.print("  running mkdocs build…")
        site_dir = publish.build(strict=strict)
        console.print(f"[bold green]✓[/bold green] site → {site_dir}")
    else:
        console.print("  [dim]skipped mkdocs build (use --build to enable)[/dim]")


if __name__ == "__main__":
    app()
