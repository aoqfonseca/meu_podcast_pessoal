"""Gemini calls: per-article summary, hot topics, reading-list table."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from .loader import Article


def build_chat(api_key: str, model: str, temperature: float = 0.4) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key,
        temperature=temperature,
    )


def summarize_article(chat: ChatGoogleGenerativeAI, article: Article) -> str:
    sys = SystemMessage(
        content=(
            "Você é um curador de tecnologia. Resuma o artigo em 3 a 5 bullets em PT-BR, "
            "focando nos pontos técnicos relevantes. Não invente; se algo não estiver no texto, "
            "omita. Não inclua introdução nem conclusão."
        )
    )
    body = (article.text[:6000]).strip()
    user = HumanMessage(
        content=(
            f"Título: {article.title or '(sem título)'}\n"
            f"Fonte: {article.source}\n"
            f"Link: {article.link or '(sem link)'}\n\n"
            f"Conteúdo:\n{body}"
        )
    )
    resp = chat.invoke([sys, user])
    return str(resp.content).strip()


def generate_hot_topics(
    chat: ChatGoogleGenerativeAI, articles: list[Article], context_excerpts: list[str]
) -> str:
    sys = SystemMessage(
        content=(
            "Você é um curador de tecnologia. Identifique 3 a 5 'tópicos quentes' do dia "
            "com base nos títulos e trechos fornecidos. Para cada tópico: nome em negrito, "
            "1 a 2 frases explicando por que importa, e quais fontes cobriram. "
            "Responda em PT-BR, em formato de bullets markdown."
        )
    )
    headlines = "\n".join(
        f"- [{a.source}] {a.title or '(sem título)'}" for a in articles
    )
    extras = "\n\n".join(context_excerpts[:10]) if context_excerpts else ""
    user = HumanMessage(
        content=(
            f"Manchetes do dia:\n{headlines}\n\n"
            f"Trechos relevantes encontrados no índice vetorial:\n{extras}"
        )
    )
    resp = chat.invoke([sys, user])
    return str(resp.content).strip()


def build_reading_table(articles: list[Article]) -> str:
    """Pure markdown table — no LLM call needed."""
    rows = ["| # | Título | Fonte | Tags | Link |", "|---|---|---|---|---|"]
    for i, a in enumerate(articles, start=1):
        title = (a.title or "(sem título)").replace("|", "\\|")
        tags = ", ".join(a.tags)
        link = a.link or ""
        link_md = f"[abrir]({link})" if link else "—"
        rows.append(f"| {i} | {title} | {a.source} | {tags} | {link_md} |")
    return "\n".join(rows)
