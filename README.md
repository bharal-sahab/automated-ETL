# automated-ETL

[![CI](https://github.com/bharal-sahab/automated-ETL/actions/workflows/ci.yml/badge.svg)](https://github.com/bharal-sahab/automated-ETL/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Clone this repo, point it at a JSON HTTP API, and you get a local FastAPI ETL: fetch → SQLite → word-count metrics + anomaly flags → optional 5-minute scheduler.

If this is useful, star the repo and fork it for your own source.

## Quick start

```bash
git clone https://github.com/bharal-sahab/automated-ETL.git
cd automated-ETL
python3.11 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Plugins, docs links |
| `GET` | `/health` | Liveness + active source/processor |
| `POST` | `/pipeline/run` | One ingest + process |
| `GET` | `/metrics` | Processed rows (`limit`, `offset`) |

Default source is [JSONPlaceholder posts](https://jsonplaceholder.typicode.com/posts). Data lives in `./pipeline.db` (created on first run). No cloud database.

```bash
pytest tests -v
```

Tests use in-memory SQLite and mock outbound HTTP. They never write `pipeline.db`.

## Use it without writing code

Edit `.env`:

**Same shape as JSONPlaceholder** (`userId`, `id`, `title`, `body`):

```env
SOURCE_NAME=jsonplaceholder
SOURCE_URL=https://jsonplaceholder.typicode.com/posts
```

**Any JSON array of objects** — map the id and text fields (dotted paths work):

```env
SOURCE_NAME=http_json
SOURCE_URL=https://your.api.example/items
SOURCE_ID_FIELD=id
SOURCE_TEXT_FIELD=body
# SOURCE_ID_FIELD=event.id
# SOURCE_TEXT_FIELD=message
```

### Authenticated and wrapped JSON

Bearer tokens and APIs that wrap the list in an object (not a root array) use optional env vars. `SOURCE_ID_FIELD` and `SOURCE_TEXT_FIELD` still apply to each element inside the list.

```env
SOURCE_NAME=http_json
SOURCE_URL=https://your.api.example/v1/posts
SOURCE_AUTH_HEADER=Authorization
SOURCE_AUTH_TOKEN=Bearer your-token
SOURCE_ITEMS_PATH=data
SOURCE_ID_FIELD=id
SOURCE_TEXT_FIELD=body
```

Use a placeholder token in `.env`; do not commit real secrets. JSONPlaceholder (`SOURCE_NAME=jsonplaceholder`) still expects a **root array** — do not set `SOURCE_ITEMS_PATH` for that source.

Then `POST /pipeline/run`. Scheduler: `SCHEDULER_ENABLED=true`, `INGESTION_INTERVAL_SECONDS=300`.

**Template repo:** To offer “Use this template” on GitHub, mark the repository as a template in **Settings → General**. Add topics such as `fastapi`, `etl`, `sqlite`, and `python` under **About** (repo owner, in the UI).

## Extend it in code

| You want to… | Do this |
| --- | --- |
| Hit a JSON array API | `SOURCE_NAME=http_json` + field env vars |
| Validate a custom payload | New class in `services/sources/`, register in `services/registry.py` |
| Change scoring / anomalies | `services/processor.py` |
| Change schedule / lock | `core/scheduler.py`, `services/pipeline.py` |
| Change storage | `db/models.py`, `db/client.py` |

`IngestedItem` is the contract: every source returns `{id, body, payload}`. The built-in `word_count` processor only needs `id` and `body`.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the register-a-source checklist.

```
fetch (plugin) → raw_ingestion → process (plugin) → processed_metrics
```

## Config

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./pipeline.db` | SQLAlchemy URL |
| `SOURCE_NAME` | `jsonplaceholder` | `jsonplaceholder` or `http_json` |
| `PROCESSOR_NAME` | `word_count` | Built-in processor |
| `SOURCE_URL` | JSONPlaceholder posts | HTTP JSON endpoint (`MOCK_API_URL` still works) |
| `SOURCE_ID_FIELD` | `id` | Id path for `http_json` |
| `SOURCE_TEXT_FIELD` | `body` | Text path for `http_json` |
| `SOURCE_AUTH_HEADER` | `Authorization` | Header name when `SOURCE_AUTH_TOKEN` is set |
| `SOURCE_AUTH_TOKEN` | *(empty)* | Sent verbatim as that header (e.g. `Bearer your-token`) |
| `SOURCE_ITEMS_PATH` | *(empty)* | Dotted path to the list on the JSON object for `http_json` |
| `INGESTION_INTERVAL_SECONDS` | `300` | Scheduler period |
| `SCHEDULER_ENABLED` | `true` | Run ingest on an interval |
| `HTTP_TIMEOUT_SECONDS` | `30` | Outbound HTTP timeout |

## License

[MIT](LICENSE) — use, fork, and ship it.
