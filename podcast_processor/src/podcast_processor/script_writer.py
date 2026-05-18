"""Generate a ~5-minute podcast narration script from the daily content."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI


def generate_podcast_script(
    chat: ChatGoogleGenerativeAI,
    hot_topics_md: str,
    article_summaries_md: str,
    minutes: int = 5,
) -> str:
    target_words = minutes * 150
    sys = SystemMessage(
        content=(
            "Você é o roteirista de um podcast diário de tecnologia em PT-BR. "
            "Escreva uma narração contínua, em primeira pessoa do plural, com tom "
            "informativo e leve. NÃO use marcações de cena, NÃO escreva 'host:', "
            "NÃO inclua música ou efeitos. Apenas o texto que será lido em voz alta. "
            "Estruture: abertura curta com saudação, bloco 'o que está pegando hoje' "
            "(tópicos quentes), bloco de destaques (resumindo 3 a 5 artigos mais "
            "interessantes), e fechamento com tendências a observar. "
            f"Mire {target_words} palavras (aproximadamente {minutes} minutos de áudio)."
        )
    )
    user = HumanMessage(
        content=(
            f"### Tópicos quentes do dia\n{hot_topics_md}\n\n"
            f"### Resumos dos artigos\n{article_summaries_md}\n\n"
            "Escreva o script agora."
        )
    )
    resp = chat.invoke([sys, user])
    return str(resp.content).strip()
