from __future__ import annotations

import pytest

# Import config at module level so load_dotenv() runs before any monkeypatch —
# otherwise a delenv() during a test would be overridden by .env reloading.
from podcast_processor import config


def test_settings_does_not_require_key_eagerly(monkeypatch):
    """from_env() no longer raises — keys are checked lazily."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    s = config.Settings.from_env()
    assert s.google_api_key == ""
    assert s.groq_api_key == ""


def test_require_google_key_raises_when_missing(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    s = config.Settings.from_env()
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        s.require_google_key()


def test_require_groq_key_raises_when_missing(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    s = config.Settings.from_env()
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        s.require_groq_key()


def test_settings_reads_google_api_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-123")
    s = config.Settings.from_env()
    assert s.google_api_key == "test-key-123"
    assert s.text_model == "gemini-2.5-flash-lite"


def test_settings_defaults_for_new_providers(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    monkeypatch.delenv("PODCAST_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("PODCAST_TTS_PROVIDER", raising=False)
    s = config.Settings.from_env()
    assert s.llm_provider == "gemini"
    assert s.tts_provider == "edge"
    assert s.groq_model == "llama-3.3-70b-versatile"
    assert s.edge_tts_voice == "pt-BR-FranciscaNeural"


def test_settings_env_overrides(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    monkeypatch.setenv("PODCAST_TEXT_MODEL", "gemini-2.5-pro")
    monkeypatch.setenv("PODCAST_TTS_VOICE", "Aoede")
    monkeypatch.setenv("PODCAST_LLM_PROVIDER", "groq")
    monkeypatch.setenv("PODCAST_GROQ_MODEL", "llama-3.1-8b-instant")
    monkeypatch.setenv("PODCAST_TTS_PROVIDER", "gemini")
    monkeypatch.setenv("PODCAST_EDGE_TTS_VOICE", "pt-BR-AntonioNeural")
    s = config.Settings.from_env()
    assert s.text_model == "gemini-2.5-pro"
    assert s.tts_voice == "Aoede"
    assert s.llm_provider == "groq"
    assert s.groq_model == "llama-3.1-8b-instant"
    assert s.tts_provider == "gemini"
    assert s.edge_tts_voice == "pt-BR-AntonioNeural"


def test_resolve_llm_gemini(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "g-key")
    monkeypatch.setenv("PODCAST_LLM_PROVIDER", "gemini")
    provider, key, model = config.Settings.from_env().resolve_llm()
    assert provider == "gemini"
    assert key == "g-key"
    assert model == "gemini-2.5-flash-lite"


def test_resolve_llm_groq(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_xyz")
    monkeypatch.setenv("PODCAST_LLM_PROVIDER", "groq")
    provider, key, model = config.Settings.from_env().resolve_llm()
    assert provider == "groq"
    assert key == "gsk_xyz"
    assert model == "llama-3.3-70b-versatile"


def test_resolve_llm_unknown_provider(monkeypatch):
    monkeypatch.setenv("PODCAST_LLM_PROVIDER", "openai")
    with pytest.raises(RuntimeError, match="unknown llm provider"):
        config.Settings.from_env().resolve_llm()
