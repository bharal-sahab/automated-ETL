# Pipeline Project State

Working memory for the FastAPI + SQLite (SQLModel) ingestion pipeline. Update this file as each phase completes.

**Python version:** 3.11.8 (`./venv`, created from `/Users/samarthbharal/.pyenv/versions/3.11.8/bin/python3`)

## Phases

- [x] Phase 1: Initialization & State Management
- [x] Phase 2: Database Architecture (SQLite + SQLModel; no Supabase)
- [x] Phase 3: Core Logic & API
- [x] Phase 4: Automation (scheduler)
- [x] Phase 5: QA & Self-Correction (in-memory SQLite tests)

## Architecture notes (Architect)

- Layout: `main.py` app factory + lifespan; packages `api/`, `core/`, `db/`, `services/`, `tests/`.
- DB: local `pipeline.db` via SQLModel (`DATABASE_URL=sqlite:///./pipeline.db`). Tables `RawIngestion` (`raw_ingestion`) and `ProcessedMetrics` (`processed_metrics`, `run_id` FK). Schema created on connect.
- Tests: `sqlite:///:memory:` with StaticPool; HTTPX/JSONPlaceholder mocked with respx. Tests do not write `pipeline.db`.
- Anomaly rule: `|word_count - mean| > 1 * population stddev`; if stddev is 0 or n < 2, no anomalies.
- Scheduler: asyncio loop, configurable interval, shared lock so runs do not overlap.

## QA log

- `./venv/bin/pytest tests -v` → **50 passed** (0.33s)
- No remaining failures.
