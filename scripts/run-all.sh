#!/usr/bin/env bash
# Run the full pipeline (leitor_links -> podcast_processor).
#
# Modes:
#   docker     (default) — uses docker compose, isolated and reproducible.
#   baremetal           — uses the local cargo + uv toolchains.
#
# Usage:
#   ./scripts/run-all.sh                    # docker mode, runs all steps
#   ./scripts/run-all.sh --mode baremetal
#   ./scripts/run-all.sh --mode docker --fetch-args "--tags IA --since-days 7"
#   ./scripts/run-all.sh --mode baremetal --process-args "--skip-audio"
#   ./scripts/run-all.sh --steps process    # skip rust fetch, only run LLM
#   ./scripts/run-all.sh --steps fetch      # only fetch, skip LLM
#
# Environment (LLM keys — only one pair is required depending on provider):
#   GOOGLE_API_KEY          required when PODCAST_LLM_PROVIDER=gemini (default).
#   GEMINI_API_KEY          alias for GOOGLE_API_KEY.
#   GROQ_API_KEY            required when PODCAST_LLM_PROVIDER=groq.
#
# Environment (optional overrides):
#   PODCAST_LLM_PROVIDER    gemini (default) | groq
#   PODCAST_TEXT_MODEL      Gemini model name  (default: gemini-2.5-flash-lite)
#   PODCAST_GROQ_MODEL      Groq model name    (default: llama-3.3-70b-versatile)
#   PODCAST_TTS_PROVIDER    edge (default, free) | gemini
#   PODCAST_TTS_MODEL       Gemini TTS model   (default: gemini-2.5-flash-preview-tts)
#   PODCAST_TTS_VOICE       Gemini TTS voice   (default: Kore)
#   PODCAST_EDGE_TTS_VOICE  Edge TTS voice     (default: pt-BR-FranciscaNeural)
#   PODCAST_EMBEDDING_MODEL Embedding model    (default: paraphrase-multilingual-MiniLM-L12-v2)
#   FETCH_ARGS              forwarded to `leitor_links fetch`.
#   PROCESS_ARGS            forwarded to `podcast-processor run`.
#   STEPS                   comma-separated list: fetch,process (default: fetch,process).

set -euo pipefail

MODE="docker"
FETCH_ARGS="${FETCH_ARGS:-}"
PROCESS_ARGS="${PROCESS_ARGS:-}"
STEPS="${STEPS:-fetch,process}"

# LLM / TTS configuration (passed through to podcast-processor).
PODCAST_LLM_PROVIDER="${PODCAST_LLM_PROVIDER:-gemini}"
PODCAST_TEXT_MODEL="${PODCAST_TEXT_MODEL:-}"
PODCAST_GROQ_MODEL="${PODCAST_GROQ_MODEL:-}"
PODCAST_TTS_PROVIDER="${PODCAST_TTS_PROVIDER:-}"
PODCAST_TTS_MODEL="${PODCAST_TTS_MODEL:-}"
PODCAST_TTS_VOICE="${PODCAST_TTS_VOICE:-}"
PODCAST_EDGE_TTS_VOICE="${PODCAST_EDGE_TTS_VOICE:-}"
PODCAST_EMBEDDING_MODEL="${PODCAST_EMBEDDING_MODEL:-}"

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
        --steps)
            STEPS="$2"
            shift 2
            ;;
        --skip-fetch)
            STEPS="process"
            shift
            ;;
        --skip-process)
            STEPS="fetch"
            shift
            ;;
        -h|--help)
            sed -n '2,32p' "$0"
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

has_step() {
    case ",$STEPS," in
        *",$1,"*) return 0 ;;
        *) return 1 ;;
    esac
}

require_api_key() {
    # Load .env if any required key is still unset.
    local needs_load=0
    [[ "${PODCAST_LLM_PROVIDER:-gemini}" == "groq" ]] && [[ -z "${GROQ_API_KEY:-}" ]] && needs_load=1
    [[ "${PODCAST_LLM_PROVIDER:-gemini}" != "groq" ]] && [[ -z "${GOOGLE_API_KEY:-}" ]] && [[ -z "${GEMINI_API_KEY:-}" ]] && needs_load=1
    if [[ "$needs_load" -eq 1 ]]; then
        if [[ -f "$REPO_ROOT/.env" ]]; then
            # shellcheck disable=SC1091
            set -a; . "$REPO_ROOT/.env"; set +a
        elif [[ -f "$REPO_ROOT/podcast_processor/.env" ]]; then
            set -a; . "$REPO_ROOT/podcast_processor/.env"; set +a
        fi
    fi

    # Accept GEMINI_API_KEY as alias for GOOGLE_API_KEY.
    if [[ -z "${GOOGLE_API_KEY:-}" ]] && [[ -n "${GEMINI_API_KEY:-}" ]]; then
        GOOGLE_API_KEY="$GEMINI_API_KEY"
    fi

    if [[ "${PODCAST_LLM_PROVIDER:-gemini}" == "groq" ]]; then
        if [[ -z "${GROQ_API_KEY:-}" ]]; then
            echo "ERROR: GROQ_API_KEY is not set (required for llm-provider=groq)." >&2
            exit 1
        fi
    else
        if [[ -z "${GOOGLE_API_KEY:-}" ]]; then
            echo "ERROR: GOOGLE_API_KEY (or GEMINI_API_KEY) is not set (and no .env file found)." >&2
            exit 1
        fi
    fi
}

run_docker() {
    if has_step process; then
        require_api_key
    fi
    if ! command -v docker >/dev/null 2>&1; then
        echo "ERROR: docker is not installed or not on PATH." >&2
        exit 1
    fi
    echo "==> docker mode (steps: $STEPS, llm: ${PODCAST_LLM_PROVIDER})"
    GOOGLE_API_KEY="${GOOGLE_API_KEY:-}" \
    GEMINI_API_KEY="${GEMINI_API_KEY:-}" \
    GROQ_API_KEY="${GROQ_API_KEY:-}" \
    PODCAST_LLM_PROVIDER="$PODCAST_LLM_PROVIDER" \
    PODCAST_TEXT_MODEL="$PODCAST_TEXT_MODEL" \
    PODCAST_GROQ_MODEL="$PODCAST_GROQ_MODEL" \
    PODCAST_TTS_PROVIDER="$PODCAST_TTS_PROVIDER" \
    PODCAST_TTS_MODEL="$PODCAST_TTS_MODEL" \
    PODCAST_TTS_VOICE="$PODCAST_TTS_VOICE" \
    PODCAST_EDGE_TTS_VOICE="$PODCAST_EDGE_TTS_VOICE" \
    PODCAST_EMBEDDING_MODEL="$PODCAST_EMBEDDING_MODEL" \
    FETCH_ARGS="$FETCH_ARGS" \
    PROCESS_ARGS="$PROCESS_ARGS" \
    STEPS="$STEPS" \
        docker compose run --rm pipeline
}

run_baremetal() {
    if has_step process; then
        require_api_key
    fi
    if has_step fetch && ! command -v cargo >/dev/null 2>&1; then
        echo "ERROR: cargo not found. Install Rust from https://rustup.rs/" >&2
        exit 1
    fi
    if has_step process && ! command -v uv >/dev/null 2>&1; then
        echo "ERROR: uv not found. Install from https://docs.astral.sh/uv/" >&2
        exit 1
    fi

    echo "==> baremetal mode (steps: $STEPS, llm: ${PODCAST_LLM_PROVIDER})"
    if has_step fetch; then
        echo "--> leitor_links fetch"
        (
            cd "$REPO_ROOT/leitor_links"
            # shellcheck disable=SC2086
            cargo run --release --quiet -- fetch $FETCH_ARGS
        )
    else
        echo "--> skipping leitor_links fetch (not in STEPS)"
    fi

    if has_step process; then
        echo "--> podcast-processor run"
        (
            cd "$REPO_ROOT/podcast_processor"
            export GOOGLE_API_KEY GEMINI_API_KEY GROQ_API_KEY
            export PODCAST_LLM_PROVIDER PODCAST_TEXT_MODEL PODCAST_GROQ_MODEL
            export PODCAST_TTS_PROVIDER PODCAST_TTS_MODEL PODCAST_TTS_VOICE PODCAST_EDGE_TTS_VOICE
            export PODCAST_EMBEDDING_MODEL
            # shellcheck disable=SC2086
            uv run podcast-processor run $PROCESS_ARGS
        )
    else
        echo "--> skipping podcast-processor (not in STEPS)"
    fi
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
