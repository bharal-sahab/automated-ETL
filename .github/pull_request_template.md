## Summary

What changed and why (one or two sentences).

## How to test

```bash
pytest tests -v
```

Note any manual steps (e.g. `SOURCE_NAME=http_json` in a local `.env` and `POST /pipeline/run`).

## Checklist

- [ ] Tests pass locally
- [ ] `.env` is not committed (only `.env.example` if env docs changed)
- [ ] `pipeline.db` and other local artifacts are not committed
- [ ] No secrets or real API tokens in the diff
