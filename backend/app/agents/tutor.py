from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from app.agents.personas import generate_reply
from app.agents.retriever import format_context, retrieve_for_tutor
from app.agents.state import PersonaResponse

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
    history = list(state["messages"])
    query = next(
        (m.content for m in reversed(history) if isinstance(m, HumanMessage)), ""
    )
    docs = retrieve_for_tutor(store, query)
    system = TUTOR_SYSTEM.format(context=format_context(docs) or "(no passages retrieved)")
    content = await generate_reply(llm, system, history, tag="persona:tutor")
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
