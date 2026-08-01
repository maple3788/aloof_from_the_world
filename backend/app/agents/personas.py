import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.i18n import language_directive, normalize_language, retrieval_query
from app.agents.retriever import format_context, retrieve_for_persona
from app.agents.state import PersonaResponse
from app.agents.trace import elapsed_ms, recorder_from

PERSONAS_DIR = Path(__file__).resolve().parents[1] / "personas"


@dataclass(frozen=True)
class PersonaCard:
    id: str
    name: str
    era: str
    tradition: str
    color: str
    authors: list[str] = field(default_factory=list)
    traditions: list[str] = field(default_factory=list)
    greeting: str = ""
    greeting_zh: str = ""
    voice: str = ""
    worldview: str = ""
    style_rules: list[str] = field(default_factory=list)

    def system_prompt(
        self,
        context: str,
        other_speakers: list[str] | None = None,
        round_so_far: str = "",
        language: str = "en",
    ) -> str:
        rules = "\n".join(f"- {r}" for r in self.style_rules)
        parts = [
            f"You are {self.name} ({self.era}), of the {self.tradition} tradition.",
            self.voice,
            f"Your worldview:\n{self.worldview}",
            f"Style rules:\n{rules}",
        ]
        if other_speakers:
            names = ", ".join(other_speakers)
            parts.append(
                f"You are in a roundtable discussion with the user and: {names}. "
                "You may agree or spar with them, but stay in your own character."
            )
        if round_so_far:
            parts.append(f"What has been said so far in this round:\n{round_so_far}")
        parts.append(
            "Primary-source passages retrieved for this turn. Ground your reply in them "
            "when relevant; you may quote briefly. Never break character.\n\n"
            f"{context or '(no passages retrieved)'}"
        )
        parts.append(language_directive(language))
        return "\n\n".join(parts)


@lru_cache
def load_personas(personas_dir: Path = PERSONAS_DIR) -> dict[str, PersonaCard]:
    personas: dict[str, PersonaCard] = {}
    for path in sorted(personas_dir.glob("*.yaml")):
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        card = PersonaCard(**data)
        personas[card.id] = card
    return personas


def get_persona(persona_id: str, personas_dir: Path = PERSONAS_DIR) -> PersonaCard:
    personas = load_personas(personas_dir)
    if persona_id not in personas:
        raise KeyError(f"Unknown persona '{persona_id}'. Available: {sorted(personas)}")
    return personas[persona_id]


def persona_for_author(author: str, personas_dir: Path = PERSONAS_DIR) -> PersonaCard | None:
    """Resolve a corpus author to the most specific card claiming them.

    Specificity = fewest authors on the card, so 'Plato' resolves to the
    plato card (authors: [Plato]) rather than socrates (authors: [Plato, Xenophon]).
    """
    matches = [c for c in load_personas(personas_dir).values() if author in c.authors]
    return min(matches, key=lambda c: (len(c.authors), c.id), default=None)


async def generate_reply(
    llm: BaseChatModel,
    system: str,
    messages: list,
    tag: str,
) -> str:
    chunks: list[str] = []
    async for chunk in llm.astream(
        [SystemMessage(content=system), *messages],
        config={"tags": [tag], "run_name": tag},
    ):
        chunks.append(str(chunk.content))
    return "".join(chunks).strip()


async def persona_turn(state: dict, llm: BaseChatModel, store) -> dict:
    speakers: list[str] = state["speakers"]
    language = normalize_language(state.get("language"))
    history = list(state["messages"])
    query = str(
        next(
            (m.content for m in reversed(history) if isinstance(m, HumanMessage)),
            "",
        )
    )
    # One translation per turn, shared by all speakers in a roundtable.
    rec = recorder_from(state)
    start = time.perf_counter()
    search_query = await retrieval_query(llm, query, language)
    if language == "zh":
        rec.record_translation(search_query, elapsed_ms(start))

    responses: list[PersonaResponse] = []
    round_so_far = ""
    names = {pid: get_persona(pid).name for pid in speakers}

    for pid in speakers:
        persona = get_persona(pid)
        start = time.perf_counter()
        docs: list[Document] = await retrieve_for_persona(
            store, persona, search_query, work_id=state.get("work_id")
        )
        rec.record_retrieval(pid, docs, elapsed_ms(start))
        others = [n for sp, n in names.items() if sp != pid]
        system = persona.system_prompt(
            format_context(docs),
            other_speakers=others,
            round_so_far=round_so_far,
            language=language,
        )
        start = time.perf_counter()
        content = await generate_reply(llm, system, history, tag=f"persona:{pid}")
        rec.record_reply(pid, elapsed_ms(start), len(content))
        round_so_far += f"\n- {persona.name}: {content}"
        responses.append(
            PersonaResponse(
                responder=pid,
                responder_name=persona.name,
                content=content,
                citations=[],
                critic_note=None,
                docs=docs,
            )
        )
    return {"responses": responses}
