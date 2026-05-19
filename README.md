# meu_podcast_pessoal

A two-stage pipeline that turns a curated list of RSS/Atom feeds into a daily, AI-narrated technology podcast in Portuguese.

```
RSS feeds  ──►  leitor_links (Rust)  ──►  JSON per source
                                              │
                                              ▼
                                       podcast_processor (Python)
                                              │
                                              ├─► FAISS index (persistent)
                                              ├─► report.md   (hot topics + summaries + reading list)
                                              ├─► podcast.txt (script)
                                              └─► podcast.mp3 / podcast.wav  (Edge TTS or Gemini TTS)
```

## Components

| Folder | Language | Purpose |
|---|---|---|
| [`leitor_links/`](./leitor_links) | Rust (async, tokio) | Reads `links_fontes.json`, fetches each feed, optionally scrapes the full article text via `readability`, and writes one JSON per source under `output/YYYY-MM-DD/`. |
| [`podcast_processor/`](./podcast_processor) | Python 3.13 (uv) | Loads those JSONs, vectorizes with local `sentence-transformers` into a persistent FAISS index, then uses Gemini 2.5 Flash + native TTS to generate the daily report and audio. |
| `links_fontes.json` | JSON | The source list (name, tags, URL per feed). Edit this to add or remove feeds. |

Each component has its own README with the full details:

- [leitor_links README](./leitor_links/README.md) — CLI flags, output format, build & test.
- [podcast_processor README](./podcast_processor/README.md) — pipeline, configuration, env vars, test coverage.

## Quick start

You need both components installed once; afterwards a daily run is two commands.

### Prerequisites

- [Rust](https://rustup.rs/) (1.85+, edition 2024)
- [`uv`](https://docs.astral.sh/uv/) (Python 3.13 will be installed automatically)
- An API key for your chosen LLM provider:
  - **Gemini** (default) — [Google AI Studio](https://aistudio.google.com/app/apikey) → `GOOGLE_API_KEY`
  - **Groq** (free tier) — [console.groq.com](https://console.groq.com) → `GROQ_API_KEY`

### One-time setup

```bash
# 1. Build the Rust fetcher
cd leitor_links
cargo build --release
cd ..

# 2. Create your .env from the template and fill in your API key(s)
cp .env.example .env
# edit .env — at minimum set GOOGLE_API_KEY or GROQ_API_KEY

# 3. Install Python dependencies
cd podcast_processor
uv sync
cd ..
```

### Daily run

A single script (`scripts/run-all.sh`) runs the full pipeline in either Docker or baremetal mode:

```bash
# Docker (default — recommended; isolated, reproducible)
./scripts/run-all.sh

# Baremetal (uses local cargo + uv)
./scripts/run-all.sh --mode baremetal

# Forward flags to either stage
./scripts/run-all.sh --fetch-args "--tags IA,Rust --since-days 7"
./scripts/run-all.sh --mode baremetal --process-args "--skip-audio"

# See all options
./scripts/run-all.sh --help
```

Or run the two stages manually:

```bash
# 1. Fetch feeds (writes leitor_links/output/YYYY-MM-DD/*.json)
cd leitor_links && cargo run --release -- fetch && cd ..

# 2. Build the podcast (writes podcast_processor/data/outputs/YYYY-MM-DD/)
cd podcast_processor && uv run podcast-processor run
```

The outputs are:

```
podcast_processor/data/outputs/YYYY-MM-DD/
├── report.md       # hot topics, reading list, per-article summaries
├── podcast.txt     # narration script
└── podcast.mp3     # audio (Edge TTS) — or podcast.wav when using Gemini TTS
```

Useful flags:

```bash
# Fetch only IA / Rust feeds, last 7 days
cargo run --release -- fetch --tags IA,Rust --since-days 7

# Generate a markdown report without TTS
uv run podcast-processor run --skip-audio

# Reuse the existing FAISS index (no re-ingest)
uv run podcast-processor run --skip-vectorize
```

See the per-component READMEs for the full list of options.

## Docker (full pipeline in one container)

A `Dockerfile` + `docker-compose.yml` at the repo root builds both components and runs the whole pipeline end-to-end. This is the easiest way to schedule a daily run (e.g. via `cron` or a CI job).

### Build & run

```bash
# Copy the template and fill in your API key(s) (file is gitignored)
cp .env.example .env

# Build the image (multi-stage: Rust → Python venv → slim runtime)
docker compose build

# Run the full pipeline once
docker compose run --rm pipeline
```

Outputs land in the same host folders the local workflow uses:

- `leitor_links/output/YYYY-MM-DD/*.json` — fetched feeds
- `podcast_processor/data/outputs/YYYY-MM-DD/` — `report.md`, `podcast.txt`, `podcast.wav`
- `podcast_processor/data/faiss_index/` — persistent FAISS index
- `podcast_processor/data/hf-cache/` — Hugging Face model cache (downloaded on first run)

### Configuration via env

All flags can be tuned without rebuilding. Set them in your root `.env` file or export them before running:

```bash
# Use Groq instead of Gemini for LLM (free tier)
PODCAST_LLM_PROVIDER=groq \
GROQ_API_KEY=gsk_... \
docker compose run --rm pipeline

# Only IA / Rust feeds, last 7 days, skip audio
FETCH_ARGS="--tags IA,Rust --since-days 7" \
PROCESS_ARGS="--skip-audio" \
docker compose run --rm pipeline

# Override TTS voice
PODCAST_TTS_VOICE=Aoede docker compose run --rm pipeline
```

**Full variable reference:**

| Variable | Default | Description |
|---|---|---|
| `GOOGLE_API_KEY` | — | Gemini API key. Required when `PODCAST_LLM_PROVIDER=gemini`. |
| `GEMINI_API_KEY` | — | Alias for `GOOGLE_API_KEY` — either one is accepted. |
| `GROQ_API_KEY` | — | Groq API key. Required when `PODCAST_LLM_PROVIDER=groq`. |
| `PODCAST_LLM_PROVIDER` | `gemini` | LLM backend: `gemini` or `groq`. |
| `PODCAST_TEXT_MODEL` | `gemini-2.5-flash-lite` | Gemini model for text generation. |
| `PODCAST_GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model (used when provider is `groq`). |
| `PODCAST_TTS_PROVIDER` | `edge` | TTS backend: `edge` (free, MP3) or `gemini` (paid, WAV). |
| `PODCAST_EDGE_TTS_VOICE` | `pt-BR-FranciscaNeural` | Voice name for Edge TTS. |
| `PODCAST_TTS_MODEL` | `gemini-2.5-flash-preview-tts` | Gemini TTS model. |
| `PODCAST_TTS_VOICE` | `Kore` | Voice name for Gemini TTS. |
| `PODCAST_EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Sentence-transformers model for FAISS. |
| `FETCH_ARGS` | — | Extra flags forwarded to `leitor_links fetch`. |
| `PROCESS_ARGS` | — | Extra flags forwarded to `podcast-processor run`. |
| `STEPS` | `fetch,process` | Comma-separated steps to run (`fetch`, `process`, or both). |

See `.env.example` at the repo root for a ready-to-copy template.

### Image notes

- Base: `python:3.13-slim-bookworm` (Debian slim — required because `torch`, `faiss-cpu`, and `sentence-transformers` only publish glibc wheels).
- Torch is pulled from the CPU-only PyTorch index, which keeps the final image ~500 MB lighter than the default CUDA build.
- Runs as a non-root user.
- The Hugging Face embedding model (~120 MB) is downloaded into the mounted `data/hf-cache` volume on first run — the image itself does not ship it.

## Editing the source list

`links_fontes.json` is the single source of truth for which feeds get pulled. Each entry is:

```json
{
  "nome": "The Rust Blog",
  "tags": ["Rust", "Systems Programming"],
  "url": "https://blog.rust-lang.org/feed.xml"
}
```

The Rust CLI re-reads it on every run; no rebuild needed.

## Contributing

Contributions are welcome. Each subproject is self-contained and has its own toolchain.

### Working on `leitor_links/` (Rust)

```bash
cd leitor_links
cargo build              # debug build
cargo test               # 18 unit tests in src/tests.rs
cargo run -- fetch --tags Rust --since-days 30 --max-items 3   # smoke test
```

When changing behavior, update or add tests in `src/tests.rs`. Pure logic should stay free of `async`/HTTP so it can be tested without the network. See [the project README](./leitor_links/README.md) for the testing checklist.

### Working on `podcast_processor/` (Python)

```bash
cd podcast_processor
uv sync                  # installs runtime + dev dependencies
uv run pytest            # 22 unit tests
uv run ruff check .      # linter
uv run ruff format .     # formatter
uv run podcast-processor info   # confirms env / models resolve correctly
```

Live API calls (Gemini, real FAISS persistence, sentence-transformers download) are kept **out** of the default test suite to keep CI free and fast. Mark integration tests with `@pytest.mark.live` if you add them. See [the project README](./podcast_processor/README.md) for the full module layout and configuration variables.

### Pre-commit hooks

This repo ships a [`pre-commit`](https://pre-commit.com/) config that runs
`ruff format`, `ruff` (with `--fix`), and `ty check` on every commit. Install
it once:

```bash
uv tool install pre-commit          # or: pipx install pre-commit
pre-commit install                  # writes .git/hooks/pre-commit
pre-commit run --all-files          # optional: first pass over the whole repo
```

The `ty` hook shells out to `uvx ty check src/` inside `podcast_processor/`,
so no extra venv is needed.

### General guidelines

- Use feature branches; open a PR against `main`.
- Keep commits scoped (one logical change per commit). Conventional prefixes (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`) are appreciated but not required.
- For Rust changes, `cargo test` must pass. For Python changes, `uv run pytest` must pass.
- Avoid committing secrets — `.env` is gitignored on purpose. Use `.env.example` to document any new variable.
- Generated artifacts (`leitor_links/target/`, `leitor_links/output/`, `podcast_processor/.venv/`, `podcast_processor/data/`) are all gitignored.

## License

This project is licensed under the [Apache License, Version 2.0](./LICENSE). You may use, modify, and redistribute it freely under the terms of that license.

```
Copyright 2026 Andre Fonseca

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0
```
