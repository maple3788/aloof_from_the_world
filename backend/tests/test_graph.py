from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage

from app.agents.graph import build_graph
from app.agents.router import router_node


class FakeStore:
    """Returns author-filtered docs so persona scoping is observable in tests."""

    def similarity_search(self, query, k=6, filter=None):
        author = "Plato"
        if filter and "$or" in filter:
            clause = filter["$or"][0]
            author = clause["author"]["$in"][0]
        elif filter and "author" in filter:
            author = filter["author"]["$in"][0]
        elif filter is None:
            author = "Whole Corpus"
        return [
            Document(
                page_content=f"Passage {i} by {author} relevant to: {query}",
                metadata={
                    "work_id": f"work_{author.lower()}",
                    "title": f"The Works of {author}",
                    "author": author,
                    "tradition": "Test tradition",
                    "era": "Test era",
                    "chunk_index": i,
                },
            )
            for i in range(2)
        ]


CRITIC_OK = '{"supported": true, "citation_indices": [1], "note": null}'


def make_llm(replies: list[str]) -> FakeListChatModel:
    return FakeListChatModel(responses=replies + [CRITIC_OK] * 4)


async def test_discuss_mode_single_persona_grounded_reply():
    graph = build_graph(
        llm=make_llm(["Virtue, my friend — is it knowledge, or something else?"]),
        store=FakeStore(),
    )
    state = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="What is virtue?")],
            "mode": "discuss",
            "persona_ids": ["socrates"],
        }
    )
    (resp,) = state["responses"]
    assert resp["responder"] == "socrates"
    assert "Virtue" in resp["content"]
    assert resp["citations"][0]["author"] == "Plato"
    assert resp["critic_note"] is None


async def test_roundtable_each_persona_speaks_from_own_corpus():
    graph = build_graph(
        llm=make_llm(["Define your terms, friend.", "Morality is herd instinct!"]),
        store=FakeStore(),
    )
    state = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="Is morality natural?")],
            "mode": "discuss",
            "persona_ids": ["socrates", "nietzsche"],
        }
    )
    responders = [r["responder"] for r in state["responses"]]
    assert responders == ["socrates", "nietzsche"]
    assert state["responses"][0]["citations"][0]["author"] == "Plato"
    assert state["responses"][1]["citations"][0]["author"] == "Friedrich Nietzsche"


async def test_router_narrows_roundtable_on_name_mention():
    state = router_node(
        {
            "messages": [HumanMessage(content="Freud, what do you make of dreams?")],
            "mode": "discuss",
            "persona_ids": ["socrates", "freud"],
        }
    )
    assert state["speakers"] == ["freud"]


async def test_study_mode_routes_to_tutor_with_citations():
    graph = build_graph(
        llm=make_llm(["Stoicism teaches apatheia... Tell me: what is in your control?"]),
        store=FakeStore(),
    )
    state = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="Explain Stoicism")],
            "mode": "study",
            "persona_ids": [],
        }
    )
    (resp,) = state["responses"]
    assert resp["responder"] == "tutor"
    assert resp["citations"][0]["author"] == "Whole Corpus"


async def test_router_defaults_unknown_mode_and_persona():
    state = router_node(
        {"messages": [HumanMessage(content="hi")], "mode": "nonsense", "persona_ids": ["nobody"]}
    )
    assert state["mode"] == "discuss"
    assert state["persona_ids"] == ["socrates"]
