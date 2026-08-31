# FastAPI + SQLite data-ingestion pipeline

Async pipeline that pulls posts from JSONPlaceholder, stores the raw payload in a local SQLite file (`pipeline.db`), computes word-count metrics, and flags anomalies. A background scheduler repeats the run on an interval.

No external database. SQLModel creates tables on startup.

## Setup

```bash
python3.11 -m venv venv   # this project was built with Python 3.11.8
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` defaults to `DATABASE_URL=sqlite:///./pipeline.db`. That file is created next to the process working directory on first connect.

## Run

```bash
source venv/bin/activate
uvicorn main:app --reload
```

- `GET /health` — liveness
- `POST /pipeline/run` — fetch, persist, process once
- `GET /metrics?limit=50&offset=0` — processed rows

The scheduler starts with the app (disable with `SCHEDULER_ENABLED=false`). Interval: `INGESTION_INTERVAL_SECONDS` (default 300).

## Test

```bash
source venv/bin/activate
pytest tests -v
```

Tests use an in-memory SQLite database (`sqlite:///:memory:`) and mock the posts HTTP API. They do not create or write `pipeline.db`.
