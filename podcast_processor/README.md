# podcast_processor

Python pipeline that turns the daily article dumps from [`leitor_links`](../leitor_links) into a Gemini-powered podcast (markdown report + audio).

## Pipeline

1. **Load** every `*.json` from `../leitor_links/output/YYYY-MM-DD/` and normalize into `Article` rows.
2. **Vectorize** each article with local `sentence-transformers` embeddings, chunked via `RecursiveCharacterTextSplitter`, persisted in a FAISS index that accumulates across days.
3. **Summarize** each article with **Gemini 2.5 Flash** (3–5 bullets in PT-BR).
4. **Hot topics** — Gemini identifies 3–5 trending themes of the day, using day headlines + retrieval over the FAISS history.
5. **Reading list** — pure markdown table (no LLM call).
6. **Podcast script** — Gemini generates ~5 min of PT-BR narration combining hot topics + summaries.
7. **TTS** — Gemini 2.5 native audio renders the script into `podcast.wav`.

## Requirements

- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- A Google Gemini API key

## Setup

```bash
cd podcast_processor
cp .env.example .env
# edit .env and set GOOGLE_API_KEY=...

uv sync
```

The first run will download the `sentence-transformers` model (~120 MB) into the local HF cache.

## Usage

Run from inside `podcast_processor/`:

```bash
# Build the podcast for the most recent day available
uv run podcast-processor run

# Specific day
uv run podcast-processor run --date 2026-05-18

# Skip audio (only markdown + script.txt)
uv run podcast-processor run --skip-audio

# Re-use the existing FAISS index without re-ingesting today
uv run podcast-processor run --skip-vectorize

# Custom paths
uv run podcast-processor run \
    --input ../leitor_links/output \
    --output ./data/outputs \
    --faiss-dir ./data/faiss_index

# Inspect configuration
uv run podcast-processor info

# List available day folders
uv run podcast-processor list
```

## Output

For a day `YYYY-MM-DD`, the run writes:

```
data/outputs/YYYY-MM-DD/
├── report.md       # markdown: hot topics, reading list, per-article summaries, audio link
├── podcast.txt     # narration script (text only)
└── podcast.wav     # generated audio (omitted with --skip-audio)
```

The FAISS index lives at `data/faiss_index/` and grows over time.

## Configuration

All settings can be overridden via env (see `.env.example`):

| Variable | Default |
|---|---|
| `GOOGLE_API_KEY` | _(required)_ |
| `PODCAST_TEXT_MODEL` | `gemini-2.5-flash` |
| `PODCAST_TTS_MODEL` | `gemini-2.5-flash-preview-tts` |
| `PODCAST_TTS_VOICE` | `Kore` |
| `PODCAST_EMBEDDING_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |

## Tests

```bash
uv run pytest
```

22 unit tests covering:

- Loader: full-text/summary/feed-content fallback, missing-text skip, ISO date parsing, day-folder resolution, listing.
- Vectorstore: chunking, sequential indices, metadata provenance, single-chunk short docs.
- Reading-table markdown: headers, numbering, pipe escaping, missing links.
- Render: section presence, conditional audio block.
- Config: missing-key error, env overrides.

Tests do not hit Gemini, FAISS persistence, or sentence-transformers download paths. To run live integration tests against Gemini, write them under `@pytest.mark.live`.

## Project layout

```
podcast_processor/
├── pyproject.toml
├── .env.example
├── src/podcast_processor/
│   ├── cli.py           # typer entrypoint (run / list / info)
│   ├── config.py        # env-based Settings
│   ├── loader.py        # JSON → Article
│   ├── vectorstore.py   # FAISS + HF embeddings
│   ├── summarizer.py    # Gemini per-article + hot topics + table
│   ├── script_writer.py # Gemini podcast script
│   ├── tts.py           # Gemini native TTS → WAV
│   └── render.py        # markdown report composer
├── tests/
│   ├── test_loader.py
│   ├── test_vectorstore.py
│   ├── test_summarizer_table.py
│   ├── test_render.py
│   └── test_config.py
└── data/                # generated; gitignored
    ├── faiss_index/
    └── outputs/YYYY-MM-DD/
```
