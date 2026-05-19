# CLAUDE.md

## Project overview

Two-stage pipeline that turns RSS/Atom feeds into a daily AI-narrated technology podcast in Portuguese.

```
leitor_links (Rust)  →  JSON per source  →  podcast_processor (Python)  →  report.md + podcast.mp3
```

## Repository layout

```
leitor_links/          Rust CLI — fetches feeds, writes output/YYYY-MM-DD/*.json
podcast_processor/     Python package — vectorizes, summarizes, scripts, synthesises audio
scripts/
  run-all.sh           Orchestrates both stages (docker or baremetal mode)
  run-pipeline.sh      Docker-only helper
docker-compose.yml     Full pipeline in one container
Dockerfile             Multi-stage: Rust build → Python venv → slim runtime
links_fontes.json      Feed source list (name, tags, url) — edit to add/remove feeds
.env.example           Template for all env vars; copy to .env and fill in keys
```

## Development commands

### leitor_links (Rust)

```bash
cd leitor_links
cargo build              # debug build
cargo build --release    # release build
cargo test               # unit tests (src/tests.rs, no network required)
cargo run --release -- fetch --tags Rust --since-days 7 --max-items 3   # smoke test
cargo run --release -- list-tags    # show available tags from links_fontes.json
```

Key CLI flags for `fetch`: `--tags`, `--match-all`, `--since-days` (default 3), `--max-items` (default 20), `--concurrency` (default 5), `--no-full-content`.

### podcast_processor (Python)

```bash
cd podcast_processor
uv sync                        # install runtime + dev deps
uv run pytest                  # unit tests (no network, no API calls)
uv run ruff check .            # linter
uv run ruff format .           # formatter
uv run podcast-processor info  # print resolved config / verify env
uv run podcast-processor run --skip-audio --skip-vectorize   # fast local test
```

Live API tests are marked `@pytest.mark.live` and excluded from the default suite.

### Full pipeline

```bash
./scripts/run-all.sh                          # docker (default)
./scripts/run-all.sh --mode baremetal         # local cargo + uv
./scripts/run-all.sh --steps process          # skip fetch, only LLM
./scripts/run-all.sh --fetch-args "--tags IA,Rust --since-days 7"
./scripts/run-all.sh --process-args "--skip-audio --minutes 10"
```

## Configuration

All config comes from env vars (loaded via `python-dotenv` from `.env` at repo root).

| Variable | Default | Notes |
|---|---|---|
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | — | Required for Gemini provider (either alias works) |
| `GROQ_API_KEY` | — | Required when `PODCAST_LLM_PROVIDER=groq` |
| `PODCAST_LLM_PROVIDER` | `gemini` | `gemini` or `groq` |
| `PODCAST_TEXT_MODEL` | `gemini-2.5-flash-lite` | Gemini text model |
| `PODCAST_GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq text model |
| `PODCAST_TTS_PROVIDER` | `edge` | `edge` (free, MP3) or `gemini` (paid, WAV) |
| `PODCAST_EDGE_TTS_VOICE` | `pt-BR-FranciscaNeural` | Edge TTS voice |
| `PODCAST_TTS_MODEL` | `gemini-2.5-flash-preview-tts` | Gemini TTS model |
| `PODCAST_TTS_VOICE` | `Kore` | Gemini TTS voice |
| `PODCAST_EMBEDDING_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | FAISS embeddings |
| `FETCH_ARGS` | — | Extra flags for `leitor_links fetch` |
| `PROCESS_ARGS` | — | Extra flags for `podcast-processor run` |
| `STEPS` | `fetch,process` | Comma-separated steps to run |

## Python module layout (`podcast_processor/src/podcast_processor/`)

| Module | Responsibility |
|---|---|
| `config.py` | `Settings` dataclass; reads env; `resolve_llm()` → `(provider, key, model)` |
| `cli.py` | Typer app: `run`, `list`, `info`, `build-site` commands |
| `loader.py` | Reads `leitor_links` JSON output into `Article` objects |
| `vectorstore.py` | FAISS ingestion + retrieval via `langchain-community` |
| `summarizer.py` | Per-article summaries + hot-topics generation; LRU disk cache |
| `script_writer.py` | Generates the podcast narration script |
| `render.py` | Renders `report.md` from summaries + hot topics |
| `tts.py` | Edge TTS (`synthesize_edge_to_mp3`) and Gemini TTS (`synthesize_to_wav`) |
| `publish.py` | Syncs outputs into MkDocs site structure; calls `mkdocs build` |

## Outputs

```
podcast_processor/data/outputs/YYYY-MM-DD/
├── report.md       # hot topics, per-article summaries, reading list
├── podcast.txt     # narration script
└── podcast.mp3     # Edge TTS audio (or podcast.wav for Gemini TTS)

podcast_processor/data/faiss_index/   # persistent FAISS index (RAG context)
podcast_processor/data/cache/         # per-article LLM summary cache
podcast_processor/data/hf-cache/      # Hugging Face model cache
leitor_links/output/YYYY-MM-DD/       # raw feed JSON from leitor_links
```

All `data/` subdirectories and `leitor_links/output/` are gitignored.

## Key conventions

- **No amending published commits** — always create new commits.
- **Conventional prefixes** appreciated: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
- **Rust changes**: `cargo test` must pass.
- **Python changes**: `uv run pytest` + `uv run ruff check .` must pass.
- **Never commit `.env`** — it is gitignored. Use `.env.example` to document new vars.
- **Integration tests** (real API calls) must be marked `@pytest.mark.live`; they are excluded from CI.
- Pre-commit hooks run `ruff format`, `ruff --fix`, and `ty check` — install with `pre-commit install`.
- Line length: 100 (ruff, Python). Edition 2024 (Rust).

## Docker notes

- Base image: `python:3.13-slim-bookworm` (glibc required for torch/faiss/sentence-transformers wheels).
- Torch uses the CPU-only PyTorch index to keep the image ~500 MB lighter.
- Runs as a non-root user inside the container.
- The HF embedding model (~120 MB) is downloaded to the mounted `data/hf-cache/` volume on first run.
