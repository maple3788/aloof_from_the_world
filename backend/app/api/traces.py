from fastapi import APIRouter, HTTPException, Query, Request

from app.db import Database

router = APIRouter()


@router.get("/traces")
async def list_traces(
    request: Request,
    session_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    database: Database = request.app.state.db
    return await database.list_traces(session_id=session_id, limit=limit, offset=offset)


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str, request: Request):
    database: Database = request.app.state.db
    trace = await database.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace
