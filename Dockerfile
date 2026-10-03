FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATABASE_URL=sqlite:////data/pipeline.db

RUN adduser --disabled-password --gecos "" --uid 10001 appuser \
    && mkdir -p /data \
    && chown appuser:appuser /data

COPY pyproject.toml README.md LICENSE ./
COPY main.py ./
COPY api ./api
COPY core ./core
COPY db ./db
COPY services ./services

RUN pip install --no-cache-dir .

USER appuser

EXPOSE 8000
VOLUME ["/data"]

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
