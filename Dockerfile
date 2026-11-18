FROM python:3.11-slim

# hnswlib (a chromadb dependency) has no prebuilt wheel for every platform and falls
# back to compiling from source.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r athena && useradd -r -g athena -d /app athena

WORKDIR /app

COPY pyproject.toml .
COPY src ./src
COPY configs ./configs

# Editable install: core/config/settings.py derives CONFIG_DIR from __file__, so the
# source tree must stay on disk at /app/src with configs/ as its sibling — a regular
# (non-editable) install would copy files into site-packages and break that lookup.
RUN pip install --no-cache-dir -e .

RUN mkdir -p data/raw data/processed data/reports && chown -R athena:athena /app

USER athena
EXPOSE 7860
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "de.ibikus.athena.web.app"]
