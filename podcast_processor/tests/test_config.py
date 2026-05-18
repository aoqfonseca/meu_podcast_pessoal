from __future__ import annotations

import importlib

import pytest


def test_settings_requires_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    config = importlib.import_module("podcast_processor.config")
    with pytest.raises(RuntimeError):
        config.Settings.from_env()


def test_settings_reads_google_api_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-123")
    config = importlib.import_module("podcast_processor.config")
    s = config.Settings.from_env()
    assert s.google_api_key == "test-key-123"
    assert s.text_model == "gemini-2.5-flash"


def test_settings_env_overrides(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    monkeypatch.setenv("PODCAST_TEXT_MODEL", "gemini-2.5-pro")
    monkeypatch.setenv("PODCAST_TTS_VOICE", "Aoede")
    config = importlib.import_module("podcast_processor.config")
    s = config.Settings.from_env()
    assert s.text_model == "gemini-2.5-pro"
    assert s.tts_voice == "Aoede"
