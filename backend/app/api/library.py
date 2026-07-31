from fastapi import APIRouter, Request

from app.agents.personas import load_personas
from app.rag.ingest import load_manifest

router = APIRouter()


@router.get("/personas")
def list_personas():
    return [
        {
            "id": card.id,
            "name": card.name,
            "era": card.era,
            "tradition": card.tradition,
            "color": card.color,
            "greeting": card.greeting,
        }
        for card in load_personas().values()
    ]


@router.get("/library/works")
def list_works(request: Request):
    """Corpus manifest enriched with per-work chunk counts (best effort)."""
    store = getattr(request.app.state, "store", None)
    works = []
    for work in load_manifest():
        chunks = 0
        if store is not None:
            try:
                result = store._collection.get(
                    where={"work_id": work["id"]}, include=[]
                )
                chunks = len(result.get("ids", []))
            except Exception:
                chunks = 0
        works.append({**{k: v for k, v in work.items()}, "chunks": chunks})
    return works
