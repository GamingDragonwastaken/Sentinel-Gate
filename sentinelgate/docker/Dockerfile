FROM python:3.11-slim-bullseye

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml MANIFEST.in ./
COPY sentinelgate/ ./sentinelgate/

RUN pip install --no-cache-dir -e .

RUN python sentinelgate/setup_lobster.py

COPY sentinelgate/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8501

ENTRYPOINT ["/entrypoint.sh"]
