"""Tests for the script writer — focuses on prompt assembly + RAG context.

We use a fake chat model that captures the last message list it was invoked
with, so we can assert what the writer sent without hitting any real API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from langchain_core.language_models import BaseChatModel

from podcast_processor.script_writer import generate_podcast_script


@dataclass
class _FakeResponse:
    content: str = "narration text"


@dataclass
class _FakeChat:
    last_messages: list = field(default_factory=list)

    def invoke(self, messages):
        self.last_messages = list(messages)
        return _FakeResponse()


def _new_chat() -> tuple[_FakeChat, BaseChatModel]:
    """Build a fake chat and return (real_ref, cast_for_type_checker)."""
    chat = _FakeChat()
    return chat, cast(BaseChatModel, chat)


def _human_content(chat: _FakeChat) -> str:
    return chat.last_messages[-1].content


def _system_content(chat: _FakeChat) -> str:
    return chat.last_messages[0].content


def test_script_writer_returns_stripped_content():
    _real, chat = _new_chat()
    out = generate_podcast_script(chat, "topics", "summaries")
    assert out == "narration text"


def test_script_writer_includes_topics_and_summaries():
    real, chat = _new_chat()
    generate_podcast_script(chat, "HOT_TOPICS_MD", "SUMMARIES_MD")
    user = _human_content(real)
    assert "HOT_TOPICS_MD" in user
    assert "SUMMARIES_MD" in user
    assert "Tópicos quentes do dia" in user
    assert "Resumos dos artigos" in user


def test_script_writer_omits_context_block_when_no_excerpts():
    real, chat = _new_chat()
    generate_podcast_script(chat, "topics", "summaries", context_excerpts=None)
    user = _human_content(real)
    assert "Cobertura anterior" not in user


def test_script_writer_omits_context_block_when_excerpts_empty():
    real, chat = _new_chat()
    generate_podcast_script(chat, "topics", "summaries", context_excerpts=[])
    user = _human_content(real)
    assert "Cobertura anterior" not in user


def test_script_writer_injects_context_excerpts_when_provided():
    real, chat = _new_chat()
    excerpts = [
        "[arXiv · 2026-05-15] previous paper on agent orchestration…",
        "[HN · 2026-05-16] discussion about MCP servers…",
    ]
    generate_podcast_script(chat, "topics", "summaries", context_excerpts=excerpts)
    user = _human_content(real)
    assert "Cobertura anterior" in user
    assert excerpts[0] in user
    assert excerpts[1] in user


def test_script_writer_system_prompt_mentions_continuity_when_context_used():
    """The system prompt always mentions continuity guidance — RAG-friendly."""
    real, chat = _new_chat()
    generate_podcast_script(chat, "topics", "summaries")
    sys = _system_content(real)
    assert "Se forem fornecidos trechos" in sys
    assert "sem inventar" in sys


def test_script_writer_target_words_scales_with_minutes():
    real, chat = _new_chat()
    generate_podcast_script(chat, "t", "s", minutes=10)
    sys = _system_content(real)
    # 10 min * 150 words = 1500
    assert "1500 palavras" in sys
    assert "10 minutos" in sys
