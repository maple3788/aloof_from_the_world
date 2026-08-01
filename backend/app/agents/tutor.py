import time

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from app.agents.i18n import language_directive, normalize_language, retrieval_query
from app.agents.personas import generate_reply
from app.agents.retriever import format_context, retrieve_for_tutor
from app.agents.state import PersonaResponse
from app.agents.trace import elapsed_ms, recorder_from

TUTOR_SYSTEM = """You are the Tutor of "Aloof from the World", a study companion for \
philosophy, psychology, and history. Your manner is that of a great seminar leader: \
clear, encouraging, and precise.

How you teach:
- Explain ideas in plain language first, then give the precise terminology.
- Ground explanations in the retrieved primary-source passages below; quote them briefly.
- Connect the topic across traditions when useful (e.g. Stoic apatheia vs Buddhist non-attachment).
- End with exactly one Socratic question that makes the student test their understanding.
- If the student asks for a quiz, produce 3 questions of increasing difficulty and wait \
for answers before revealing your model answers.
- Admit uncertainty; never invent quotations or facts not in the sources.

Primary-source passages retrieved for this turn:

{context}"""


async def tutor_turn(state: dict, llm: BaseChatModel, store) -> dict:
    language = normalize_language(state.get("language"))
    history = list(state["messages"])
    query = str(
        next(
            (m.content for m in reversed(history) if isinstance(m, HumanMessage)),
            "",
        )
    )
    rec = recorder_from(state)
    start = time.perf_counter()
    search_query = await retrieval_query(llm, query, language)
    if language == "zh":
        rec.record_translation(search_query, elapsed_ms(start))
    start = time.perf_counter()
    docs = await retrieve_for_tutor(store, search_query)
    rec.record_retrieval("tutor", docs, elapsed_ms(start))
    system = TUTOR_SYSTEM.format(
        context=format_context(docs) or "(no passages retrieved)"
    )
    system += f"\n\n{language_directive(language)}"
    start = time.perf_counter()
    content = await generate_reply(llm, system, history, tag="persona:tutor")
    rec.record_reply("tutor", elapsed_ms(start), len(content))
    return {
        "responses": [
            PersonaResponse(
                responder="tutor",
                responder_name="Tutor",
                content=content,
                citations=[],
                critic_note=None,
                docs=docs,
            )
        ]
    }
