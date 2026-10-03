# automated-ETL

[![CI](https://github.com/bharal-sahab/automated-ETL/actions/workflows/ci.yml/badge.svg)](https://github.com/bharal-sahab/automated-ETL/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Clone this repo, point it at a JSON HTTP API, and you get a local FastAPI ETL: fetch → SQLite → scored metrics + anomaly flags → optional 5-minute scheduler.

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

**Upgrading:** If you already have a `pipeline.db` from before record ids became text, delete that file once so SQLite can recreate tables with `post_id` as text. The test suite does not use your local `pipeline.db`.

## Record ids are text

Every ingested row gets a string id (`IngestedItem.id`). JSONPlaceholder’s integer ids are stored as `"1"`, `"2"`, and so on. Metrics and API responses use the same string in `post_id`.

For `SOURCE_NAME=http_json`, `SOURCE_ID_FIELD` (dotted paths allowed) can read integers, numeric strings, UUIDs, or slug strings from each object. Values are normalized to non-empty text; blank or whitespace-only ids are rejected.

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

### Paginated `http_json`

Set **either** `SOURCE_NEXT_FIELD` **or** `SOURCE_PAGE_PARAM` — not both. Link-based pagination needs an object response, so `SOURCE_NEXT_FIELD` also requires `SOURCE_ITEMS_PATH`. Page-number pagination works on a root array or on a list at `SOURCE_ITEMS_PATH`.

| Setting | Default | Behavior |
| --- | --- | --- |
| `SOURCE_NEXT_FIELD` | *(empty)* | Dotted path to the next page URL on each JSON object (e.g. `next` or `links.next`). Missing, null, or blank stops pagination. Requires `SOURCE_ITEMS_PATH`. A non-string next value is rejected. The same `SOURCE_AUTH_*` header is sent on every page. |
| `SOURCE_PAGE_PARAM` | *(empty)* | Query parameter name (e.g. `page`). The client starts at `1` and stops when a page returns an empty item list. Works with a root array or `SOURCE_ITEMS_PATH`. |
| `SOURCE_MAX_PAGES` | `10` | Maximum HTTP GETs per fetch; exceeding it is an error. A repeated next URL is also an error. |

JSONPlaceholder is unchanged (one request). `http_json` with both pagination settings empty is still a single GET. All pages are ingested in one pipeline run; duplicate ids across pages are rejected.

Example (link-based next page):

```env
SOURCE_NAME=http_json
SOURCE_ITEMS_PATH=data
SOURCE_NEXT_FIELD=next
SOURCE_ID_FIELD=id
SOURCE_TEXT_FIELD=body
```

### Processors

Set `PROCESSOR_NAME` in `.env` (default `word_count`).

| Processor | What it scores | Anomaly rule |
| --- | --- | --- |
| `word_count` | Words in the text field (`body` for JSONPlaceholder; `SOURCE_TEXT_FIELD` for `http_json`) | More than one standard deviation from the batch mean word count |
| `numeric` | The number at `SOURCE_VALUE_FIELD` on each row (dotted path, same idea as `SOURCE_ID_FIELD`) | More than one standard deviation from the batch mean of those numbers |

Example: sensor readings as a JSON array with `id` and `reading`:

```env
SOURCE_NAME=http_json
SOURCE_URL=https://example.test/readings
SOURCE_ID_FIELD=id
SOURCE_VALUE_FIELD=reading
PROCESSOR_NAME=numeric
```

You still set `SOURCE_TEXT_FIELD` for `http_json` if the payload has a text column the source should carry through; `numeric` only needs the value path above.

Then `POST /pipeline/run`. Scheduler: `SCHEDULER_ENABLED=true`, `INGESTION_INTERVAL_SECONDS=300`.

**Template repo:** To offer “Use this template” on GitHub, mark the repository as a template in **Settings → General**. Add topics such as `fastapi`, `etl`, `sqlite`, and `python` under **About** (repo owner, in the UI).

## Extend it in code

| You want to… | Do this |
| --- | --- |
| Hit a JSON array API | `SOURCE_NAME=http_json` + field env vars |
| Validate a custom payload | New class in `services/sources/`, register in `services/registry.py` |
| Change scoring / anomalies | `services/processor.py`, register in `services/registry.py`, set `PROCESSOR_NAME` |
| Change schedule / lock | `core/scheduler.py`, `services/pipeline.py` |
| Change storage | `db/models.py`, `db/client.py` |

`IngestedItem` is the contract: every source returns `{id, body, payload}` with string `id`. `word_count` uses `body`; `numeric` reads the configured value field from each row’s payload.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the register-a-source checklist.

```
fetch (plugin) → raw_ingestion → process (plugin) → processed_metrics
```

## Config

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./pipeline.db` | SQLAlchemy URL |
| `SOURCE_NAME` | `jsonplaceholder` | `jsonplaceholder` or `http_json` |
| `PROCESSOR_NAME` | `word_count` | `word_count` or `numeric` |
| `SOURCE_URL` | JSONPlaceholder posts | HTTP JSON endpoint (`MOCK_API_URL` still works) |
| `SOURCE_ID_FIELD` | `id` | Id path for `http_json` (stored as text) |
| `SOURCE_TEXT_FIELD` | `body` | Text path for `http_json` (used by `word_count`) |
| `SOURCE_VALUE_FIELD` | *(empty)* | Numeric path for `http_json` when `PROCESSOR_NAME=numeric` |
| `SOURCE_AUTH_HEADER` | `Authorization` | Header name when `SOURCE_AUTH_TOKEN` is set |
| `SOURCE_AUTH_TOKEN` | *(empty)* | Sent verbatim as that header (e.g. `Bearer your-token`) |
| `SOURCE_ITEMS_PATH` | *(empty)* | Dotted path to the list on the JSON object for `http_json` |
| `SOURCE_NEXT_FIELD` | *(empty)* | Dotted path to the next page URL on each JSON object for `http_json`; requires `SOURCE_ITEMS_PATH`; do not set with `SOURCE_PAGE_PARAM` |
| `SOURCE_PAGE_PARAM` | *(empty)* | Query parameter for page-number pagination (starts at 1); root array or `SOURCE_ITEMS_PATH`; do not set with `SOURCE_NEXT_FIELD` |
| `SOURCE_MAX_PAGES` | `10` | Maximum GETs per `http_json` fetch (error if exceeded) |
| `INGESTION_INTERVAL_SECONDS` | `300` | Scheduler period |
| `SCHEDULER_ENABLED` | `true` | Run ingest on an interval |
| `HTTP_TIMEOUT_SECONDS` | `30` | Outbound HTTP timeout |

## License

[MIT](LICENSE) — use, fork, and ship it.
