import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.agents.graph import build_graph
from app.api import chat, library, sessions
from app.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    app.state.graph = build_graph()
    try:
        from app.rag.store import get_vector_store

        app.state.store = get_vector_store()
    except Exception:
        logger.warning(
            "Vector store unavailable at startup; retrieval will fail lazily", exc_info=True
        )
        app.state.store = None
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Aloof from the World", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(sessions.router, tags=["sessions"])
    app.include_router(chat.router, tags=["chat"])
    app.include_router(library.router, tags=["library"])

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "llm_provider": settings.llm_provider.value,
            "embedding_provider": settings.embedding_provider.value,
        }

    return app


app = create_app()
