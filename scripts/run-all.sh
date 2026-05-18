#!/usr/bin/env bash
# Run the full pipeline (leitor_links -> podcast_processor).
#
# Modes:
#   docker     (default) — uses docker compose, isolated and reproducible.
#   baremetal           — uses the local cargo + uv toolchains.
#
# Usage:
#   ./scripts/run-all.sh                    # docker mode
#   ./scripts/run-all.sh --mode baremetal
#   ./scripts/run-all.sh --mode docker --fetch-args "--tags IA --since-days 7"
#   ./scripts/run-all.sh --mode baremetal --process-args "--skip-audio"
#
# Environment:
#   GOOGLE_API_KEY  required in both modes.
#   FETCH_ARGS      forwarded to `leitor_links fetch`.
#   PROCESS_ARGS    forwarded to `podcast-processor run`.

set -euo pipefail

MODE="docker"
FETCH_ARGS="${FETCH_ARGS:-}"
PROCESS_ARGS="${PROCESS_ARGS:-}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -m|--mode)
            MODE="$2"
            shift 2
            ;;
        --fetch-args)
            FETCH_ARGS="$2"
            shift 2
            ;;
        --process-args)
            PROCESS_ARGS="$2"
            shift 2
            ;;
        -h|--help)
            sed -n '2,18p' "$0"
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            echo "Use --help for usage." >&2
            exit 2
            ;;
    esac
done

# Resolve repo root regardless of where the script is called from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

require_api_key() {
    if [[ -z "${GOOGLE_API_KEY:-}" ]]; then
        if [[ -f "$REPO_ROOT/.env" ]]; then
            # shellcheck disable=SC1091
            set -a; . "$REPO_ROOT/.env"; set +a
        elif [[ -f "$REPO_ROOT/podcast_processor/.env" ]]; then
            set -a; . "$REPO_ROOT/podcast_processor/.env"; set +a
        fi
    fi
    if [[ -z "${GOOGLE_API_KEY:-}" ]]; then
        echo "ERROR: GOOGLE_API_KEY is not set (and no .env file found)." >&2
        exit 1
    fi
}

run_docker() {
    require_api_key
    if ! command -v docker >/dev/null 2>&1; then
        echo "ERROR: docker is not installed or not on PATH." >&2
        exit 1
    fi
    echo "==> docker mode"
    GOOGLE_API_KEY="$GOOGLE_API_KEY" \
    FETCH_ARGS="$FETCH_ARGS" \
    PROCESS_ARGS="$PROCESS_ARGS" \
        docker compose run --rm pipeline
}

run_baremetal() {
    require_api_key
    if ! command -v cargo >/dev/null 2>&1; then
        echo "ERROR: cargo not found. Install Rust from https://rustup.rs/" >&2
        exit 1
    fi
    if ! command -v uv >/dev/null 2>&1; then
        echo "ERROR: uv not found. Install from https://docs.astral.sh/uv/" >&2
        exit 1
    fi

    echo "==> baremetal mode"
    echo "--> [1/2] leitor_links fetch"
    (
        cd "$REPO_ROOT/leitor_links"
        # shellcheck disable=SC2086
        cargo run --release --quiet -- fetch $FETCH_ARGS
    )

    echo "--> [2/2] podcast-processor run"
    (
        cd "$REPO_ROOT/podcast_processor"
        export GOOGLE_API_KEY
        # shellcheck disable=SC2086
        uv run podcast-processor run $PROCESS_ARGS
    )
}

case "$MODE" in
    docker)    run_docker ;;
    baremetal) run_baremetal ;;
    *)
        echo "ERROR: unknown --mode '$MODE' (expected: docker | baremetal)" >&2
        exit 2
        ;;
esac

echo "==> Pipeline finished."
