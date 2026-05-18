# leitor_links

Async Rust CLI that reads a list of RSS/Atom feeds from a JSON file, fetches recent items from each, optionally scrapes the full article text, and saves one JSON file per source for downstream processing (e.g. a Python pipeline).

## Features

- Reads sources from a JSON file (`../links_fontes.json` by default).
- Filters sources by tag (OR by default, AND with `--match-all`).
- Date window filter — keeps only items published in the last N days (default: 3).
- Concurrent fetching across sources with configurable concurrency.
- Optional full-page scraping via [`readability`](https://crates.io/crates/readability) (enabled by default).
- One JSON output file per source, grouped under `output/YYYY-MM-DD/`.
- Failures in a single source do not abort the run; a summary is printed at the end.

## Input format

The CLI expects a JSON array of source objects:

```json
[
  {
    "nome": "arXiv Artificial Intelligence",
    "tags": ["Papers", "IA", "LLM", "Agents"],
    "url": "http://export.arxiv.org/rss/cs.AI"
  }
]
```

Required fields: `nome`, `tags`, `url`.

## Output format

Each successful source produces `output/YYYY-MM-DD/<slug>.json`:

```json
{
  "fonte": "The Rust Blog",
  "tags": ["Rust", "Systems Programming"],
  "url": "https://blog.rust-lang.org/feed.xml",
  "fetched_at": "2026-05-18T14:32:00Z",
  "item_count": 3,
  "items": [
    {
      "title": "...",
      "link": "...",
      "published": "2026-05-17T10:00:00Z",
      "summary": "...",
      "feed_content": "...",
      "full_text": "...",
      "scrape_error": null
    }
  ]
}
```

`full_text` is the extracted article body when `--no-full-content` is not set. If scraping a particular item fails, `full_text` will be `null` and `scrape_error` will contain a message.

## Requirements

- Rust 1.85+ (edition 2024).
- Network access to the feed URLs and the article pages.

## Build

```bash
cargo build --release
```

The binary will be at `./target/release/leitor_links`.

For development, `cargo build` (debug profile) is fine and faster to compile.

## Usage

### Fetch all sources (default behavior)

```bash
cargo run -- fetch
```

This reads `../links_fontes.json`, keeps items from the last 3 days, fetches up to 20 items per source, scrapes full text, and writes results under `./output/YYYY-MM-DD/`.

### Filter by tag (OR)

```bash
cargo run -- fetch --tags IA,Rust
```

### Filter by tag (AND — must match all)

```bash
cargo run -- fetch --tags IA,LLM --match-all
```

### Tune the date window and item count

```bash
cargo run -- fetch --since-days 7 --max-items 30
```

### Skip full-page scraping (feed content only — much faster)

```bash
cargo run -- fetch --no-full-content
```

### Increase concurrency

```bash
cargo run -- fetch --concurrency 10
```

### Custom input / output paths

```bash
cargo run -- fetch --input /path/to/sources.json --output /path/to/out
```

### Discovery commands

```bash
cargo run -- list-tags      # prints every tag found in the sources file
cargo run -- list-sources   # prints "name [tags] — url" for each source
```

## All `fetch` flags

| Flag | Default | Description |
|---|---|---|
| `-i, --input <PATH>` | `../links_fontes.json` | Path to the sources JSON file. |
| `-o, --output <PATH>` | `./output` | Output directory (a `YYYY-MM-DD` subdir is created inside). |
| `-t, --tags <CSV>` | _(empty)_ | Comma-separated tags to filter sources. Empty = all sources. |
| `--match-all` | `false` | Require ALL provided tags (AND) instead of any (OR). |
| `--since-days <N>` | `3` | Only keep items published in the last N days. |
| `--max-items <N>` | `20` | Maximum number of items per source. |
| `--concurrency <N>` | `5` | Number of sources fetched in parallel. |
| `--no-full-content` | `false` | Disable full-page scraping; keep only feed content. |

## Tests

```bash
cargo test
```

Runs 18 unit tests covering:

- Tag filtering (OR / AND / case-insensitive / empty / no-match).
- `Fonte` JSON deserialization (real schema, missing fields, file loading).
- `filter_and_sort_entries` (date cutoff, sort order, truncation, `updated` fallback, items without dates).
- Feed parsing for both RSS 2.0 and Atom.
- End-to-end parse-then-filter pipeline.
- Filename slug generation (spaces, parentheses, accents).
- `DateTime<Utc>` RFC 3339 serialization (guard against output format drift for downstream Python consumers).

Tests live in `src/tests.rs` as a child module — no `pub` exposure required.

## Project layout

```
leitor_links/
├── Cargo.toml
├── README.md
├── src/
│   ├── main.rs        # CLI, async runtime, fetch/scrape logic
│   └── tests.rs       # unit tests (child module of main.rs)
└── output/            # generated; gitignored
    └── 2026-05-18/
        ├── arxiv-artificial-intelligence.json
        ├── the-rust-blog.json
        └── ...
```

## Notes

- `output/` and `target/` are gitignored.
- The default `--input` path (`../links_fontes.json`) assumes the CLI is run from the `leitor_links/` directory, with the sources file living one level up. Override with `--input` if your layout differs.
- An item without a publication date is kept (not filtered out by `--since-days`), since some feeds omit `pubDate`.
- The HTTP client uses a 30s timeout per request and identifies itself as `leitor_links/0.1`.
