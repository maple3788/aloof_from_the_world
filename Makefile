.PHONY: setup ingest backend frontend repl test docker

setup:
	cd backend && uv sync
	cd frontend && npm install

ingest:
	cd backend && uv run python -m app.rag.ingest

backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

repl:
	cd backend && uv run python -m app.cli

test:
	cd backend && uv run pytest -q
	cd frontend && npm run lint && npm test

docker:
	docker compose up --build
