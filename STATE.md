# Pipeline Project State

Working memory for the FastAPI + SQLite (SQLModel) ingestion pipeline.

**Python version:** 3.11.8

## Phases

- [x] Phase 1: Initialization & State Management
- [x] Phase 2: Database Architecture (SQLite + SQLModel)
- [x] Phase 3: Core Logic & API
- [x] Phase 4: Automation (scheduler)
- [x] Phase 5: QA & Self-Correction
- [x] Clone-and-extend template (plugins, LICENSE, CI, docs)

## Architecture notes

- Plugins: `SOURCE_NAME=jsonplaceholder|http_json`, `PROCESSOR_NAME=word_count`.
- Generic JSON arrays: `http_json` + `SOURCE_ID_FIELD` / `SOURCE_TEXT_FIELD` (dotted paths).
- Custom sources: `services/sources/` + `register_source` / `SOURCE_FACTORIES`.
- Tests: `sqlite:///:memory:`; HTTP mocked with respx.
