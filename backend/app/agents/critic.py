import asyncio
import json
import re

from langchain_core.language_models import BaseChatModel

from app.agents.i18n import normalize_language
from app.agents.retriever import doc_to_excerpt, format_context
from app.agents.state import Citation, PersonaResponse
from app.agents.trace import recorder_from
from app.cache import critic_key, get_cache
from app.config import get_settings

MAX_CITATIONS = 3

CRITIC_PROMPT = """You are a grounding critic. A speaker gave the response below, \
using only the numbered source passages.

RESPONSE:
{response}

SOURCE PASSAGES:
{context}

Decide which passages genuinely support the response's claims. Reply with ONLY a \
JSON object, no other text:
{{"supported": true|false, "citation_indices": [ints from the passage numbers], \
"note": "one short sentence if the response overreaches its sources, else null"}}{note_language}"""


def _doc_to_citation(doc) -> Citation:
    return Citation(
        work_id=doc.metadata.get("work_id", ""),
        title=doc.metadata.get("title", "Unknown work"),
        author=doc.metadata.get("author", "Unknown author"),
        era=doc.metadata.get("era", ""),
        chunk_index=doc.metadata.get("chunk_index", 0),
        excerpt=doc_to_excerpt(doc),
    )


def _heuristic_citations(docs, limit: int = MAX_CITATIONS) -> list[Citation]:
    seen: set[tuple[str, int]] = set()
    citations: list[Citation] = []
    for doc in docs:
        key = (doc.metadata.get("work_id", ""), doc.metadata.get("chunk_index", 0))
        if key in seen:
            continue
        seen.add(key)
        citations.append(_doc_to_citation(doc))
        if len(citations) >= limit:
            break
    return citations


def _parse_critic_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data.get("citation_indices"), list):
        return None
    return data


async def _critique_one(
    response: PersonaResponse,
    llm: BaseChatModel | None,
    enabled: bool,
    language: str = "en",
    recorder=None,
) -> PersonaResponse:
    docs = response.get("docs") or []
    citations = _heuristic_citations(docs)
    note: str | None = None
    supported: bool | None = None
    from_cache = False

    if enabled and llm is not None and docs:
        context = format_context(docs)
        cache = get_cache()
        # Language is part of the prompt, so it must be part of the cache key.
        key = critic_key(response["content"], f"{language}:{context}")
        data = await cache.get(key)
        if data is not None:
            from_cache = True
        else:
            prompt = CRITIC_PROMPT.format(
                response=response["content"],
                context=context,
                note_language=(
                    '\nWrite the "note" value in Simplified Chinese (简体中文).'
                    if language == "zh"
                    else ""
                ),
            )
            try:
                result = await llm.ainvoke(prompt, config={"tags": ["critic"]})
                data = _parse_critic_json(str(result.content))
            except Exception:
                data = None
            if data:
                await cache.set(key, data, get_settings().cache_ttl_critic)
        if data:
            supported = bool(data.get("supported"))
            indices = [i for i in data["citation_indices"] if isinstance(i, int)]
            chosen = [docs[i - 1] for i in indices if 1 <= i <= len(docs)]
            if chosen:
                citations = _heuristic_citations(chosen)
            if data.get("supported") is False and data.get("note"):
                note = str(data["note"])

    if recorder is not None:
        recorder.record_critic(
            response["responder"], supported, note, len(citations), from_cache
        )

    return PersonaResponse(
        responder=response["responder"],
        responder_name=response["responder_name"],
        content=response["content"],
        citations=citations,
        critic_note=note,
        docs=[],
    )


async def critic_node(
    state: dict, llm: BaseChatModel | None = None, enabled: bool = True
) -> dict:
    language = normalize_language(state.get("language"))
    recorder = recorder_from(state)
    # Responses are independent post-generation, so critiques run concurrently.
    reviewed = await asyncio.gather(
        *(
            _critique_one(r, llm, enabled, language, recorder)
            for r in state.get("responses", [])
        )
    )
    return {"responses": list(reviewed)}
