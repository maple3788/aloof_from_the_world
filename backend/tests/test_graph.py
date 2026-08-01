from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage

from app.agents.graph import build_graph
from app.agents.router import router_node
from app.agents.trace import TraceRecorder


class FakeStore:
    """Returns author-filtered docs so persona scoping is observable in tests."""

    def __init__(self):
        self.queries: list[str] = []

    def similarity_search(self, query, k=6, filter=None):
        self.queries.append(query)
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


async def test_router_normalizes_language():
    state = router_node({"messages": [HumanMessage(content="hi")], "language": "fr"})
    assert state["language"] == "en"
    state = router_node({"messages": [HumanMessage(content="hi")], "language": "zh"})
    assert state["language"] == "zh"


async def test_chinese_turn_translates_query_before_retrieval():
    store = FakeStore()
    graph = build_graph(
        llm=make_llm(["What is virtue?", "朋友，敢问何谓美德？"]),
        store=store,
    )
    state = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="什么是美德？")],
            "mode": "discuss",
            "language": "zh",
            "persona_ids": ["socrates"],
        }
    )
    (resp,) = state["responses"]
    assert resp["content"] == "朋友，敢问何谓美德？"
    assert state["language"] == "zh"
    # Retrieval ran with the translated English query, not the Chinese original.
    assert store.queries[0] == "What is virtue?"


async def test_english_turn_retrieves_without_translation():
    store = FakeStore()
    graph = build_graph(
        llm=make_llm(["Virtue is knowledge, friend."]),
        store=store,
    )
    await graph.ainvoke(
        {
            "messages": [HumanMessage(content="What is virtue?")],
            "mode": "discuss",
            "language": "en",
            "persona_ids": ["socrates"],
        }
    )
    # First (and only) retrieval query is the original — no translation hop.
    assert store.queries[0] == "What is virtue?"


async def test_trace_recorder_captures_full_chinese_turn():
    rec = TraceRecorder("t1", "s1", "什么是美德？", "discuss", "zh")
    graph = build_graph(
        llm=make_llm(["What is virtue?", "朋友，敢问何谓美德？"]),
        store=FakeStore(),
    )
    await graph.ainvoke(
        {
            "messages": [HumanMessage(content="什么是美德？")],
            "mode": "discuss",
            "language": "zh",
            "persona_ids": ["socrates"],
            "trace": rec,
        }
    )
    row = rec.finish("ok", None, ["socrates"])
    detail = row["detail"]
    assert detail["retrieval_query"] == "What is virtue?"
    assert detail["translation_ms"] is not None
    (retrieval,) = detail["retrievals"]
    assert retrieval["persona"] == "socrates"
    assert [d["title"] for d in retrieval["docs"]] == ["The Works of Plato"] * 2
    (reply,) = detail["replies"]
    assert reply["persona"] == "socrates" and reply["chars"] > 0
    (verdict,) = detail["critic"]
    assert verdict["supported"] is True and verdict["from_cache"] is False


async def test_trace_recorder_english_turn_has_no_translation_span():
    rec = TraceRecorder("t2", "s1", "What is virtue?", "discuss", "en")
    graph = build_graph(
        llm=make_llm(["Virtue is knowledge, friend."]),
        store=FakeStore(),
    )
    await graph.ainvoke(
        {
            "messages": [HumanMessage(content="What is virtue?")],
            "mode": "discuss",
            "language": "en",
            "persona_ids": ["socrates"],
            "trace": rec,
        }
    )
    detail = rec.finish("ok", None, ["socrates"])["detail"]
    assert detail["translation_ms"] is None
    assert len(detail["retrievals"]) == 1
