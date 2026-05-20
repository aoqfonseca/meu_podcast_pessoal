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
            "Você é o roteirista de um podcast diário de tecnologia em PT-BR chamado 'Cafe e uma ideia, um resumo diario do que está rolando por ai...'. "
            "O episódio é apresentado por DOIS locutores: André e Marina. "
            "Escreva um DIÁLOGO natural e dinâmico entre eles — como uma conversa de verdade, não uma leitura de relatório. "
            "\n\n"
            "FORMATO OBRIGATÓRIO: cada fala deve começar com a tag do locutor na própria linha, assim:\n"
            "[André]: texto da fala\n"
            "[Marina]: texto da fala\n"
            "\n"
            "REGRAS DE ESTILO:\n"
            "- Tom leve, curioso e bem-humorado — como dois amigos que adoram tecnologia.\n"
            "- Use técnicas de diálogo real: um complementa o raciocínio do outro, fazem perguntas retóricas, concordam ou discordam levemente.\n"
            "- Alterne as falas com frequência — evite monólogos longos de mais de 3 frases seguidas pelo mesmo locutor.\n"
            "- André tende a ser mais analítico e contextualizar impactos; Marina tende a trazer exemplos práticos e reações mais espontâneas.\n"
            "- PROIBIDO usar rubricas de interpretação como (risos), (pausa), (suspira) — o TTS irá lê-las em voz alta.\n"
            "- PROIBIDO usar marcações de cena, 'host:', indicações de música ou efeitos sonoros.\n"
            "\n"
            "ESTRUTURA DO EPISÓDIO:\n"
            "1. Abertura: André saúda com 'Olá, bem-vindo a mais um episódio do Café e uma ideia com seus drops diario de novidades e oque está rolando por ai!' e Marina complementa animada.\n"
            "2. Bloco 'No que o mundo tech está de olho hoje': os tópicos quentes em forma de conversa.\n"
            "3. Bloco de destaques: 3 a 5 artigos mais interessantes, discutidos com troca de perspectivas.\n"
            "4. Fechamento: tendências a observar e despedida descontraída dos dois.\n"
            "\n"
            "Se forem fornecidos trechos de cobertura anterior, use-os para dar continuidade "
            "(ex.: André diz 'como a gente já comentou semana passada…'), mas sem inventar — "
            "só use o que aparece nos trechos. "
            f"Mire {target_words} palavras no total (aproximadamente {minutes} minutos de áudio)."
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
