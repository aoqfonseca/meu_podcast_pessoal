from __future__ import annotations

from datetime import datetime, timezone

from podcast_processor.loader import Article
from podcast_processor.vectorstore import articles_to_documents


def _make_article(text: str, title: str = "t") -> Article:
    return Article(
        source="src",
        tags=["a", "b"],
        source_url="http://x",
        title=title,
        link="http://x/1",
        published=datetime(2026, 5, 18, tzinfo=timezone.utc),
        text=text,
    )


def test_chunking_produces_multiple_documents_for_long_text():
    long_text = "frase de teste. " * 500  # ~8000 chars
    art = _make_article(long_text)
    docs = articles_to_documents([art], "2026-05-18", chunk_size=500, chunk_overlap=50)
    assert len(docs) > 1
    assert all(d.metadata["source"] == "src" for d in docs)
    assert all(d.metadata["day"] == "2026-05-18" for d in docs)


def test_chunk_indexes_are_sequential():
    art = _make_article("x " * 1000)
    docs = articles_to_documents([art], "2026-05-18", chunk_size=200, chunk_overlap=20)
    idxs = [d.metadata["chunk_index"] for d in docs]
    assert idxs == list(range(len(docs)))


def test_metadata_contains_full_provenance():
    art = _make_article("texto curto", title="Meu Título")
    docs = articles_to_documents([art], "2026-05-18", chunk_size=1000, chunk_overlap=100)
    meta = docs[0].metadata
    assert meta["source"] == "src"
    assert meta["tags"] == "a, b"
    assert meta["title"] == "Meu Título"
    assert meta["link"] == "http://x/1"
    assert meta["published"].startswith("2026-05-18")


def test_short_text_produces_single_chunk():
    art = _make_article("texto bem curto")
    docs = articles_to_documents([art], "2026-05-18", chunk_size=1000, chunk_overlap=100)
    assert len(docs) == 1
