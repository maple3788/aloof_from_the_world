from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.agents.critic import _heuristic_citations, _parse_critic_json, critic_node


def doc(work: str, i: int) -> Document:
    return Document(
        page_content=f"Excerpt {i} from {work}. " * 10,
        metadata={
            "work_id": work,
            "title": work.title(),
            "author": "Some Author",
            "era": "Antiquity",
            "chunk_index": i,
        },
    )


def test_heuristic_citations_dedup_and_cap():
    docs = [
        doc("republic", 1),
        doc("republic", 1),
        doc("republic", 2),
        doc("tao", 1),
        doc("tao", 2),
    ]
    citations = _heuristic_citations(docs, limit=3)
    assert len(citations) == 3
    keys = {(c["work_id"], c["chunk_index"]) for c in citations}
    assert len(keys) == 3
    assert all(c["excerpt"] for c in citations)


def test_parse_critic_json_extracts_object_from_prose():
    text = 'Sure! {"supported": true, "citation_indices": [1, 3], "note": null} — done'
    data = _parse_critic_json(text)
    assert data == {"supported": True, "citation_indices": [1, 3], "note": None}


def test_parse_critic_json_rejects_garbage():
    assert _parse_critic_json("no json here") is None
    assert _parse_critic_json('{"supported": true}') is None


async def test_critic_node_reviews_all_responses_in_order():
    def resp(pid: str, chunk: int) -> dict:
        return {
            "responder": pid,
            "responder_name": pid.title(),
            "content": f"{pid} speaks.",
            "citations": [],
            "critic_note": None,
            "docs": [doc("republic", chunk)],
        }

    llm = FakeListChatModel(
        responses=['{"supported": true, "citation_indices": [1], "note": null}']
    )
    out = await critic_node(
        {"responses": [resp("a", 1), resp("b", 2), resp("c", 3)]}, llm=llm, enabled=True
    )
    assert [r["responder"] for r in out["responses"]] == ["a", "b", "c"]
    assert all(r["citations"] for r in out["responses"])
