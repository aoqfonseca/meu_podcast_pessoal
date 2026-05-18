# podcast_processor

Python pipeline that turns the daily article dumps from [`leitor_links`](../leitor_links) into a
PT-BR podcast (markdown report + audio) and, optionally, a static blog site ready for GitHub Pages.

LLM and TTS backends are pluggable — pick the combination that fits your budget:

| Layer | Default | Alternative |
|---|---|---|
| LLM (summaries + script) | **Gemini 2.5 Flash Lite** | **Groq** (free tier: Llama 3.3 70B) |
| TTS (audio) | **Edge TTS** (free, no key, outputs MP3) | Gemini 2.5 native TTS (paid, outputs WAV) |

## Pipeline

1. **Load** every `*.json` from `../leitor_links/output/YYYY-MM-DD/` and normalize into `Article` rows.
2. **Vectorize** each article with local `sentence-transformers` embeddings, chunked via `RecursiveCharacterTextSplitter`, persisted in a FAISS index that accumulates across days.
3. **Summarize** each article with the configured LLM (3–5 bullets in PT-BR) — cached per article.
4. **Hot topics** — the LLM identifies 3–5 trending themes of the day, using day headlines + retrieval over the FAISS history.
5. **Reading list** — pure markdown table (no LLM call).
6. **Podcast script** — the LLM generates ~5 min of PT-BR narration combining hot topics + summaries.
7. **TTS** — Edge TTS (default) or Gemini TTS renders the script into `podcast.mp3` / `podcast.wav`.
8. **Site (optional)** — `build-site` turns the day outputs into a MkDocs Material blog.

## Requirements

- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- For Gemini: a Google Gemini API key
- For Groq: a Groq API key (free at <https://console.groq.com>)
- Edge TTS needs **no key** — it uses Microsoft's public endpoint

## Setup

```bash
cd podcast_processor
cp .env.example .env
# edit .env — at minimum set GOOGLE_API_KEY (or GROQ_API_KEY if switching LLM)

uv sync
# add --extra site if you also want to build the static blog
uv sync --extra site
```

The first run downloads the `sentence-transformers` model (~120 MB) into the local HF cache.

## Usage

Run from inside `podcast_processor/`:

```bash
# Build the podcast for the most recent day (defaults: gemini LLM + edge TTS)
uv run podcast-processor run

# Specific day
uv run podcast-processor run --date 2026-05-18

# Use Groq for the LLM (free tier)
uv run podcast-processor run --llm-provider groq

# Override the model for the active provider
uv run podcast-processor run --llm-provider groq --llm-model llama-3.1-8b-instant

# Use Gemini for TTS instead of Edge
uv run podcast-processor run --tts-provider gemini

# Skip audio entirely
uv run podcast-processor run --skip-audio

# Re-use the existing FAISS index without re-ingesting today
uv run podcast-processor run --skip-vectorize

# Custom paths
uv run podcast-processor run \
    --input ../leitor_links/output \
    --output ./data/outputs \
    --faiss-dir ./data/faiss_index

# Inspect resolved configuration
uv run podcast-processor info

# List available day folders
uv run podcast-processor list
```

### CLI flags (`run`)

| Flag | Default | Description |
|---|---|---|
| `--date` | latest | `YYYY-MM-DD`, `today`, or `latest` |
| `--input` | `../leitor_links/output` | Root with `YYYY-MM-DD/` subfolders |
| `--output` | `./data/outputs` | Where to write report + audio |
| `--faiss-dir` | `./data/faiss_index` | Persistent FAISS index |
| `--cache-dir` | `./data/cache` | Per-article summary cache |
| `--minutes` | `5` | Target podcast length |
| `--skip-audio` | off | Don't run TTS |
| `--skip-vectorize` | off | Skip FAISS ingestion (still loads for retrieval) |
| `--no-cache` | off | Disable summary cache |
| `--refresh-cache` | off | Recompute summaries even if cached |
| `--llm-provider` | `gemini` | `gemini` or `groq` |
| `--llm-model` | provider default | Override the model name |
| `--tts-provider` | `edge` | `edge` (free, MP3) or `gemini` (paid, WAV) |

## Building the static blog (GitHub Pages)

The `build-site` command turns every `data/outputs/YYYY-MM-DD/` folder into a post in a
MkDocs Material blog (PT-BR theme, dark-mode toggle, paginated archive). Audio is embedded as
an HTML5 `<audio>` player.

```bash
uv sync --extra site
uv run podcast-processor build-site         # generates posts + runs `mkdocs build`
uv run podcast-processor build-site --no-build  # just sync posts, skip build
uv run mkdocs serve -f site_src/mkdocs.yml  # local preview
```

The built site lands in `./site/`. A GitHub Actions workflow (`.github/workflows/deploy-site.yml`)
auto-publishes it to GitHub Pages on every push to `main`.

### CLI flags (`build-site`)

| Flag | Default | Description |
|---|---|---|
| `--output` | `./data/outputs` | Source folder with day outputs |
| `--build / --no-build` | `--build` | Run `mkdocs build` after syncing posts |
| `--strict` | off | Fail on mkdocs warnings |
| `--skip-audio` | off | Don't copy MP3 files into the site |

## Output

For a day `YYYY-MM-DD`, the `run` command writes:

```
data/outputs/YYYY-MM-DD/
├── report.md       # markdown: hot topics, reading list, per-article summaries, audio link
├── podcast.txt     # narration script (text only)
└── podcast.mp3     # generated audio (Edge TTS) — or podcast.wav with --tts-provider gemini
```

The FAISS index lives at `data/faiss_index/`, the summary cache at `data/cache/summaries/`, and
the generated site at `site/`.

## Configuration

All settings can be overridden via env (see `.env.example`):

### LLM

| Variable | Default | Notes |
|---|---|---|
| `PODCAST_LLM_PROVIDER` | `gemini` | `gemini` or `groq` |
| `GOOGLE_API_KEY` | — | Required when provider is `gemini` |
| `GROQ_API_KEY` | — | Required when provider is `groq` |
| `PODCAST_TEXT_MODEL` | `gemini-2.5-flash-lite` | Gemini model name |
| `PODCAST_GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model name |

### TTS

| Variable | Default | Notes |
|---|---|---|
| `PODCAST_TTS_PROVIDER` | `edge` | `edge` (free, MP3) or `gemini` (paid, WAV) |
| `PODCAST_EDGE_TTS_VOICE` | `pt-BR-FranciscaNeural` | Any Edge `pt-BR-*` voice |
| `PODCAST_TTS_MODEL` | `gemini-2.5-flash-preview-tts` | Gemini TTS model |
| `PODCAST_TTS_VOICE` | `Kore` | Gemini prebuilt voice name |

List available Edge PT-BR voices:

```bash
uv run python -c "import asyncio, edge_tts; \
  print('\n'.join(v['ShortName'] for v in asyncio.run(edge_tts.list_voices()) if v['Locale'].startswith('pt')))"
```

### Embeddings

| Variable | Default |
|---|---|
| `PODCAST_EMBEDDING_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |

## Cost notes

- **Cheapest setup (zero API cost beyond Groq free tier):** `--llm-provider groq --tts-provider edge`
  — Groq's free tier comfortably covers a daily run; Edge TTS is always free.
- **Default setup:** Gemini Flash Lite (cents/run) + Edge TTS (free). TTS is normally the dominant
  cost driver for podcast generation, so Edge TTS is a big saver.
- **Highest quality (paid):** keep both on Gemini — `--tts-provider gemini` produces the most
  natural-sounding PT-BR voice but writes WAV (you'll want to convert to MP3 before publishing).

## Tests

```bash
uv run pytest
```

Unit tests cover loader, vectorstore, reading-table markdown, render, and config. They do not
hit any external API. To add live integration tests, mark them with `@pytest.mark.live`.

## Project layout

```
podcast_processor/
├── pyproject.toml
├── .env.example
├── src/podcast_processor/
│   ├── cli.py           # typer entrypoint (run / build-site / list / info)
│   ├── config.py        # env-based Settings
│   ├── loader.py        # JSON → Article
│   ├── vectorstore.py   # FAISS + HF embeddings
│   ├── summarizer.py    # provider-agnostic chat (Gemini / Groq)
│   ├── script_writer.py # podcast script generation
│   ├── tts.py           # Edge TTS (MP3) + Gemini TTS (WAV)
│   ├── render.py        # markdown report composer
│   └── publish.py       # static-site builder (MkDocs Material)
├── site_src/            # MkDocs source for the static blog
│   ├── mkdocs.yml
│   └── docs/
│       ├── index.md
│       ├── blog/
│       └── audio/
├── tests/
└── data/                # generated
    ├── faiss_index/
    ├── cache/
    └── outputs/YYYY-MM-DD/
```
