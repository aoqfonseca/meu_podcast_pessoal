"""FAISS-based vector store using local sentence-transformers embeddings."""

from __future__ import annotations

from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .loader import Article


def build_embeddings(model_name: str) -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=model_name,
        encode_kwargs={"normalize_embeddings": True},
    )


def articles_to_documents(
    articles: list[Article],
    day_iso: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    docs: list[Document] = []
    for art in articles:
        chunks = splitter.split_text(art.best_text)
        for idx, chunk in enumerate(chunks):
            docs.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "day": day_iso,
                        "source": art.source,
                        "tags": ", ".join(art.tags),
                        "title": art.title or "",
                        "link": art.link or "",
                        "published": art.published.isoformat() if art.published else "",
                        "chunk_index": idx,
                    },
                )
            )
    return docs


def load_or_create(
    index_dir: Path,
    embeddings: HuggingFaceEmbeddings,
) -> FAISS | None:
    """Load an existing FAISS index, or return None if none exists yet."""
    if (index_dir / "index.faiss").exists():
        return FAISS.load_local(
            str(index_dir),
            embeddings,
            allow_dangerous_deserialization=True,
        )
    return None


def ingest(
    documents: list[Document],
    index_dir: Path,
    embeddings: HuggingFaceEmbeddings,
) -> FAISS:
    """Add documents to a persistent FAISS index (creating it if needed)."""
    index_dir.mkdir(parents=True, exist_ok=True)
    existing = load_or_create(index_dir, embeddings)
    if existing is None:
        store = FAISS.from_documents(documents, embeddings)
    else:
        existing.add_documents(documents)
        store = existing
    store.save_local(str(index_dir))
    return store
