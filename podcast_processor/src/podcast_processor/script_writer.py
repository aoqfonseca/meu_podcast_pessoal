"""Generate a ~5-minute podcast narration script from the daily content."""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage


def generate_podcast_script(
    chat: BaseChatModel,
    hot_topics_md: str,
    article_summaries_md: str,
    minutes: int = 5,
    context_excerpts: list[str] | None = None,
) -> str:
    """Generate the narration script.

    `context_excerpts` is an optional list of pre-formatted snippets retrieved
    from the FAISS history (RAG). When present, the writer is told to use them
    for cross-day continuity — referencing past coverage when relevant, without
    inventing facts.
    """
    target_words = minutes * 150
    sys = SystemMessage(
        content=(
            "Você é o roteirista de um podcast diário de tecnologia em PT-BR. "
            "Escreva uma narração contínua, em primeira pessoa do plural, com tom "
            "informativo e leve. NÃO use marcações de cena, NÃO escreva 'host:', "
            "NÃO inclua música ou efeitos. Apenas o texto que será lido em voz alta. "
            "Estruture: abertura curta com saudação "Olá bem vindo para mais um episodio", bloco 'os assuntos que estão chamando a atenção' "
            "(tópicos quentes), bloco de destaques (resumindo 3 a 5 artigos mais "
            "interessantes), e fechamento com tendências a observar. "
            "Se forem fornecidos trechos de cobertura anterior, use-os para dar "
            "profundidade e continuidade (ex.: 'como já vimos em outros episódios…'), mas "
            "sem inventar — só use o que aparece nos trechos. "
            f"Mire {target_words} palavras (aproximadamente {minutes} minutos de áudio)."
        )
    )
    parts = [
        f"### Tópicos quentes do dia\n{hot_topics_md}",
        f"### Resumos dos artigos\n{article_summaries_md}",
    ]
    if context_excerpts:
        joined = "\n\n".join(context_excerpts)
        parts.append(
            "### Cobertura anterior (recuperada do histórico — use para continuidade)\n"
            + joined
        )
    parts.append("Escreva o script agora.")
    user = HumanMessage(content="\n\n".join(parts))
    resp = chat.invoke([sys, user])
    return str(resp.content).strip()
