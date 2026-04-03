ARG BASE=python:3.11-slim
FROM $BASE AS builder

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir . \
    && python -m spacy download de_core_news_lg

# Runtime
ARG BASE
FROM $BASE

WORKDIR /app/data
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ /app/src/

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

EXPOSE 4141

HEALTHCHECK --interval=10s --timeout=3s --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:4141/health')"

CMD ["python", "-m", "pii_guard.server"]
