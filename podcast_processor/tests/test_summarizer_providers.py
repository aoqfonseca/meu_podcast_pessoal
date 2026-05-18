"""Tests for the provider-aware build_chat() factory."""

from __future__ import annotations

import pytest

from podcast_processor.summarizer import build_chat


def test_build_chat_gemini_returns_chat_google_generative_ai():
    from langchain_google_genai import ChatGoogleGenerativeAI

    chat = build_chat("gemini", "dummy-key", "gemini-2.5-flash-lite")
    assert isinstance(chat, ChatGoogleGenerativeAI)


def test_build_chat_groq_returns_chat_groq():
    from langchain_groq import ChatGroq

    chat = build_chat("groq", "dummy-key", "llama-3.3-70b-versatile")
    assert isinstance(chat, ChatGroq)


def test_build_chat_provider_name_is_case_insensitive():
    from langchain_groq import ChatGroq

    chat = build_chat("GROQ", "dummy-key", "llama-3.3-70b-versatile")
    assert isinstance(chat, ChatGroq)


def test_build_chat_unknown_provider_raises():
    with pytest.raises(ValueError, match="unknown llm provider"):
        build_chat("openai", "k", "gpt-4")


def test_build_chat_passes_temperature():
    chat = build_chat("gemini", "dummy", "gemini-2.5-flash-lite", temperature=0.9)
    # Access via getattr to avoid type-checker complaints — BaseChatModel
    # doesn't expose `temperature` generically.
    assert getattr(chat, "temperature") == 0.9
