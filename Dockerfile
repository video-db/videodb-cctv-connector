# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN --mount=type=secret,id=github_token \
    set -eu; \
    if [ -s /run/secrets/github_token ]; then \
      TOKEN="$(cat /run/secrets/github_token)"; \
      git config --global url."https://x-access-token:${TOKEN}@github.com/".insteadOf "https://github.com/"; \
    fi; \
    pip install --no-cache-dir -r requirements.txt; \
    if [ -n "${TOKEN:-}" ]; then \
      git config --global --unset-all url."https://x-access-token:${TOKEN}@github.com/".insteadOf || true; \
    fi

COPY push_stream.py push_feed.sh ./
RUN chmod +x /app/push_stream.py /app/push_feed.sh

ENTRYPOINT ["python", "/app/push_stream.py"]
