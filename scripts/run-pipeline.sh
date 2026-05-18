#!/usr/bin/env sh
set -eu

INPUT_JSON="${INPUT_JSON:-/app/links_fontes.json}"
LEITOR_OUTPUT="${LEITOR_OUTPUT:-/app/output}"
PODCAST_OUTPUT="${PODCAST_OUTPUT:-/app/data/outputs}"
FAISS_DIR="${FAISS_DIR:-/app/data/faiss_index}"
FETCH_ARGS="${FETCH_ARGS:-}"
PROCESS_ARGS="${PROCESS_ARGS:-}"
STEPS="${STEPS:-fetch,process}"

has_step() {
    case ",$STEPS," in
        *",$1,"*) return 0 ;;
        *) return 1 ;;
    esac
}

if has_step fetch; then
    echo "==> Fetching feeds with leitor_links"
    # shellcheck disable=SC2086
    leitor_links fetch \
        --input "$INPUT_JSON" \
        --output "$LEITOR_OUTPUT" \
        $FETCH_ARGS
else
    echo "==> Skipping fetch step (STEPS=$STEPS)"
fi

if has_step process; then
    echo "==> Building podcast with podcast_processor"
    # shellcheck disable=SC2086
    podcast-processor run \
        --input "$LEITOR_OUTPUT" \
        --output "$PODCAST_OUTPUT" \
        --faiss-dir "$FAISS_DIR" \
        $PROCESS_ARGS
else
    echo "==> Skipping process step (STEPS=$STEPS)"
fi

echo "==> Done"
