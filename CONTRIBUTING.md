# Contributing

Thanks for forking [automated-ETL](https://github.com/bharal-sahab/automated-ETL).

## Setup

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
pytest tests -v
```

## Add a data source

1. Create `services/sources/my_source.py` with a class that has `name`, `origin`, and `async def fetch(self) -> list[IngestedItem]`.
2. Register it in `services/registry.py`:

```python
SOURCE_FACTORIES = {
    "jsonplaceholder": JsonPlaceholderSource,
    "http_json": HttpJsonSource,
    "my_source": MySource,
}
```

Or call `register_source("my_source", MySource)` at import time.

3. Set `SOURCE_NAME=my_source` in `.env`.
4. Add tests under `tests/` that mock HTTPX and use `sqlite:///:memory:`.

For many public APIs you do not need a new class: set `SOURCE_NAME=http_json` and map fields with `SOURCE_ID_FIELD` / `SOURCE_TEXT_FIELD` (and `SOURCE_VALUE_FIELD` when using `PROCESSOR_NAME=numeric`). Record ids are always strings in storage and in API responses.

Built-in processors: `word_count` (text) and `numeric` (value at `SOURCE_VALUE_FIELD`, same dotted-path style as `SOURCE_ID_FIELD`). If you pull these docs onto an older checkout that still has integer `post_id` in an existing `pipeline.db`, delete that file once locally so SQLite can recreate the schema; tests use `sqlite:///:memory:` only.

## Add a processor

Keep scoring in `services/processor.py` (or a new module), then add the name to `PROCESSORS` in `services/registry.py` and wire it in `services/pipeline.py`. Cover the rule with unit tests.

## Environment and issues

Optional source settings (`SOURCE_AUTH_HEADER`, `SOURCE_AUTH_TOKEN`, `SOURCE_ITEMS_PATH`, `SOURCE_VALUE_FIELD` for `numeric`) are documented in [`.env.example`](.env.example) and the README. Use the [bug report](.github/ISSUE_TEMPLATE/bug_report.md) or [feature request](.github/ISSUE_TEMPLATE/feature_request.md) templates when opening issues, and the [pull request template](.github/pull_request_template.md) when you submit a PR.

## Pull requests

- No secrets (`.env`, keys, `pipeline.db`).
- Tests must pass (`pytest tests -v`).
- Match the existing async / Pydantic style.
