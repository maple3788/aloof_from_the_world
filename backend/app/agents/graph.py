from langgraph.graph import END, START, StateGraph

from app.agents.critic import critic_node
from app.agents.personas import persona_turn
from app.agents.router import router_node
from app.agents.state import AgentState
from app.agents.tutor import tutor_turn
from app.config import get_settings
from app.llm import get_chat_model
from app.rag.store import get_vector_store


def build_graph(llm=None, store=None, critic_enabled: bool | None = None):
    """Assemble the StateGraph: router -> respond -> critic.

    llm/store are injectable so tests can run the graph with fakes; when
    omitted they are built lazily from settings on first use.
    """
    settings = get_settings()
    if critic_enabled is None:
        critic_enabled = settings.critic_enabled
    _llm, _store = llm, store

    def get_llm():
        nonlocal _llm
        if _llm is None:
            _llm = get_chat_model(settings)
        return _llm

    def get_store():
        nonlocal _store
        if _store is None:
            _store = get_vector_store(settings)
        return _store

    async def _router(state: dict) -> dict:
        return router_node(state)

    async def _respond(state: dict) -> dict:
        if state["mode"] == "study":
            return await tutor_turn(state, get_llm(), get_store())
        return await persona_turn(state, get_llm(), get_store())

    async def _critic(state: dict) -> dict:
        return await critic_node(state, llm=get_llm(), enabled=critic_enabled)

    graph = StateGraph(AgentState)
    graph.add_node("router", _router)
    graph.add_node("respond", _respond)
    graph.add_node("critic", _critic)
    graph.add_edge(START, "router")
    graph.add_edge("router", "respond")
    graph.add_edge("respond", "critic")
    graph.add_edge("critic", END)
    return graph.compile()
