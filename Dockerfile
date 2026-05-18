# syntax=docker/dockerfile:1.7

# ---------- Stage 1: build the Rust fetcher ----------
FROM rust:1.86-slim-bookworm AS rust-builder
RUN apt-get update && \
    apt-get install -y --no-install-recommends pkg-config libssl-dev && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY leitor_links/ ./leitor_links/
WORKDIR /build/leitor_links
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/build/leitor_links/target \
    cargo build --release && \
    cp target/release/leitor_links /tmp/leitor_links && \
    strip /tmp/leitor_links

# ---------- Stage 2: build the Python venv ----------
FROM python:3.13-slim-bookworm AS python-builder
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_PROGRESS=1
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /usr/local/bin/
WORKDIR /app/podcast_processor
COPY podcast_processor/pyproject.toml podcast_processor/uv.lock podcast_processor/README.md ./
COPY podcast_processor/src ./src
# CPU-only torch keeps the image roughly 500 MB smaller than the default CUDA build.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev \
        --extra-index-url https://download.pytorch.org/whl/cpu

# ---------- Stage 3: runtime ----------
FROM python:3.13-slim-bookworm AS runtime

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd --system app && \
    useradd --system --gid app --create-home --home-dir /home/app app

# Rust binary
COPY --from=rust-builder /tmp/leitor_links /usr/local/bin/leitor_links

# Python project + venv
COPY --from=python-builder /app/podcast_processor /app/podcast_processor

# Source feed list (read by leitor_links via --input)
COPY links_fontes.json /app/links_fontes.json
COPY scripts/run-pipeline.sh /usr/local/bin/run-pipeline.sh
RUN chmod +x /usr/local/bin/run-pipeline.sh

ENV PATH="/app/podcast_processor/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/data/hf-cache \
    HF_HUB_DISABLE_TELEMETRY=1 \
    TRANSFORMERS_OFFLINE=0

# Volumes for fetched JSONs, FAISS index, podcast outputs, and HF cache.
VOLUME ["/app/output", "/app/data"]

RUN mkdir -p /app/output /app/data && chown -R app:app /app
USER app
WORKDIR /app

ENTRYPOINT ["/usr/local/bin/run-pipeline.sh"]
