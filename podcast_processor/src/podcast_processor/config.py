"""Configuration loaded from env + sensible defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = PROJECT_ROOT.parent

DEFAULT_INPUT_ROOT = REPO_ROOT / "leitor_links" / "output"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "outputs"
DEFAULT_FAISS_DIR = PROJECT_ROOT / "data" / "faiss_index"
DEFAULT_CACHE_DIR = PROJECT_ROOT / "data" / "cache"


@dataclass(frozen=True)
class Settings:
    google_api_key: str
    text_model: str = "gemini-2.5-flash-lite"
    tts_model: str = "gemini-2.5-flash-preview-tts"
    tts_voice: str = "Kore"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    chunk_size: int = 1000
    chunk_overlap: int = 150
    target_podcast_minutes: int = 5

    @classmethod
    def from_env(cls) -> "Settings":
        key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError(
                "GOOGLE_API_KEY (or GEMINI_API_KEY) not set. Put it in podcast_processor/.env"
            )
        return cls(
            google_api_key=key,
            text_model=os.getenv("PODCAST_TEXT_MODEL", "gemini-2.5-flash-lite"),
            tts_model=os.getenv("PODCAST_TTS_MODEL", "gemini-2.5-flash-preview-tts"),
            tts_voice=os.getenv("PODCAST_TTS_VOICE", "Kore"),
            embedding_model=os.getenv(
                "PODCAST_EMBEDDING_MODEL",
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            ),
        )
