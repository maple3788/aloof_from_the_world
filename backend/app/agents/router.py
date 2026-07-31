from langchain_core.messages import HumanMessage

from app.agents.personas import load_personas
from app.config import get_settings

DEFAULT_MODE = "discuss"
DEFAULT_PERSONA = "socrates"
VALID_MODES = {"discuss", "study"}


def router_node(state: dict) -> dict:
    """Moderator: normalize the request and decide who speaks this turn.

    Deterministic by design — the UI sends mode and selected personas, and a
    persona name mentioned in the message narrows a roundtable to that speaker.
    """
    settings = get_settings()
    personas = load_personas()

    mode = state.get("mode") or DEFAULT_MODE
    if mode not in VALID_MODES:
        mode = DEFAULT_MODE

    persona_ids = [pid for pid in (state.get("persona_ids") or []) if pid in personas]
    if not persona_ids:
        persona_ids = [DEFAULT_PERSONA]
    persona_ids = persona_ids[: settings.roundtable_max_personas]

    speakers = list(persona_ids) if mode == "discuss" else []

    if len(speakers) > 1:
        last = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None,
        )
        if last:
            text = str(last.content).lower()
            mentioned = [
                pid
                for pid in speakers
                if personas[pid].name.lower() in text or pid in text
            ]
            if mentioned:
                speakers = mentioned

    return {"mode": mode, "persona_ids": persona_ids, "speakers": speakers}
