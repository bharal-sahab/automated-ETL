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

For many public APIs you do not need a new class: set `SOURCE_NAME=http_json` and map fields with `SOURCE_ID_FIELD` / `SOURCE_TEXT_FIELD`.

## Add a processor

Keep scoring in `services/processor.py` (or a new module), then add the name to `PROCESSORS` in `services/registry.py` and branch in `services/pipeline.py`. Cover the rule with unit tests.

## Pull requests

- No secrets (`.env`, keys, `pipeline.db`).
- Tests must pass (`pytest tests -v`).
- Match the existing async / Pydantic style.
