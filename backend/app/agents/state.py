from typing import Annotated, Any, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class Citation(TypedDict):
    work_id: str
    title: str
    author: str
    era: str
    chunk_index: int
    excerpt: str


class PersonaResponse(TypedDict, total=False):
    responder: str  # persona id, or "tutor"
    responder_name: str
    content: str
    citations: list[Citation]
    critic_note: str | None
    docs: list[Document]  # internal only; stripped before leaving the critic


class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    mode: str  # "discuss" | "study"
    language: str  # "en" | "zh"
    persona_ids: list[str]  # 1 persona = dialogue, several = roundtable
    speakers: list[str]  # personas speaking this turn (router output)
    responses: list[PersonaResponse]
    work_id: str | None  # reading sessions: scope persona retrieval to this work
    trace: Any  # per-request TraceRecorder (agents/trace.py); never serialized
