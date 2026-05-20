"""Configuration loaded from env + sensible defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PROJECT_ROOT.parent

DEFAULT_INPUT_ROOT = REPO_ROOT / "leitor_links" / "output"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "outputs"
DEFAULT_FAISS_DIR = PROJECT_ROOT / "data" / "faiss_index"
DEFAULT_CACHE_DIR = PROJECT_ROOT / "data" / "cache"


@dataclass(frozen=True)
class Settings:
    google_api_key: str
    groq_api_key: str
    llm_provider: str = "gemini"  # "gemini" or "groq"
    text_model: str = "gemini-2.5-flash-lite"
    groq_model: str = "llama-3.3-70b-versatile"
    tts_provider: str = "edge"  # "edge" (free) or "gemini"
    tts_model: str = "gemini-2.5-flash-preview-tts"
    tts_voice: str = "Kore"          # Gemini voice for Marina (first speaker)
    tts_voice_2: str = "Puck"        # Gemini voice for André (second speaker)
    edge_tts_voice: str = "pt-BR-FranciscaNeural"   # Edge voice for Marina
    edge_tts_voice_2: str = "pt-BR-AntonioNeural"   # Edge voice for André
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    chunk_size: int = 1000
    chunk_overlap: int = 150
    target_podcast_minutes: int = 5

    @classmethod
    def from_env(cls) -> "Settings":
        google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
        groq_key = os.getenv("GROQ_API_KEY") or ""
        return cls(
            google_api_key=google_key,
            groq_api_key=groq_key,
            llm_provider=os.getenv("PODCAST_LLM_PROVIDER", "gemini"),
            text_model=os.getenv("PODCAST_TEXT_MODEL", "gemini-2.5-flash-lite"),
            groq_model=os.getenv("PODCAST_GROQ_MODEL", "llama-3.3-70b-versatile"),
            tts_provider=os.getenv("PODCAST_TTS_PROVIDER", "edge"),
            tts_model=os.getenv("PODCAST_TTS_MODEL", "gemini-2.5-flash-preview-tts"),
            tts_voice=os.getenv("PODCAST_TTS_VOICE", "Kore"),
            tts_voice_2=os.getenv("PODCAST_TTS_VOICE_2", "Puck"),
            edge_tts_voice=os.getenv("PODCAST_EDGE_TTS_VOICE", "pt-BR-FranciscaNeural"),
            edge_tts_voice_2=os.getenv("PODCAST_EDGE_TTS_VOICE_2", "pt-BR-AntonioNeural"),
            embedding_model=os.getenv(
                "PODCAST_EMBEDDING_MODEL",
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            ),
        )

    def require_google_key(self) -> str:
        if not self.google_api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY (or GEMINI_API_KEY) not set. Put it in podcast_processor/.env"
            )
        return self.google_api_key

    def require_groq_key(self) -> str:
        if not self.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY not set. Get a free key at https://console.groq.com and put it in podcast_processor/.env"
            )
        return self.groq_api_key

    def resolve_llm(self) -> tuple[str, str, str]:
        """Return (provider, api_key, model) for the configured LLM."""
        provider = self.llm_provider.lower()
        if provider == "gemini":
            return provider, self.require_google_key(), self.text_model
        if provider == "groq":
            return provider, self.require_groq_key(), self.groq_model
        raise RuntimeError(f"unknown llm provider: {self.llm_provider!r}")
