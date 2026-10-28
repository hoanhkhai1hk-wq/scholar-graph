# syntax=docker/dockerfile:1
# Both services build from tracked source. No credentials or PDFs are build inputs.
ARG NODE_IMAGE=node:22.23.4-bookworm-slim
ARG PYTHON_IMAGE=python:3.12.15-slim-bookworm

FROM ${NODE_IMAGE} AS frontend-dependencies
WORKDIR /app/frontend
ENV NEXT_TELEMETRY_DISABLED=1
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    for attempt in 1 2 3; do \
      npm ci --no-audit --no-fund --fetch-retries=3 --fetch-timeout=600000 && break; \
      if [ "$attempt" -eq 3 ]; then exit 1; fi; \
      echo "Public npm download failed; bounded retry $attempt/3"; sleep 5; \
    done

FROM frontend-dependencies AS frontend-build
# NEXT_PUBLIC values are embedded at build time; this URL is never a secret.
ENV NEXT_PUBLIC_API_BASE_URL=http://backend:8000
COPY frontend/ ./
RUN npm run build

FROM ${NODE_IMAGE} AS frontend
ARG SCHOLAR_GRAPH_REVISION=unknown
LABEL org.opencontainers.image.revision=${SCHOLAR_GRAPH_REVISION}
WORKDIR /app/frontend
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_API_BASE_URL=http://backend:8000
COPY --from=frontend-build --chown=node:node /app/frontend ./
USER node
EXPOSE 3000
CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]

FROM ${PYTHON_IMAGE} AS vector-runtime
COPY backend/requirements-retrieval.txt /tmp/requirements-retrieval.txt
# Separate from PaddleOCR's dependencies; public CPU wheels only, no credentials.
RUN python -m venv --copies /opt/vector-venv \
    && /opt/vector-venv/bin/python -m pip install --no-cache-dir --timeout 60 pip==26.2.2 \
    && /opt/vector-venv/bin/python -m pip install --no-cache-dir --timeout 60 --resume-retries 20 --index-url https://download.pytorch.org/whl/cpu torch==2.14.1+cpu \
    && /opt/vector-venv/bin/python -m pip install --no-cache-dir --timeout 60 --resume-retries 20 -r /tmp/requirements-retrieval.txt \
    && /opt/vector-venv/bin/python -m pip check \
    && /opt/vector-venv/bin/python -c "from pathlib import Path; import subprocess,sys; subprocess.run([str(Path(sys.executable).resolve()), '-c', 'import torch, chromadb, FlagEmbedding'], check=True)"

FROM ${PYTHON_IMAGE} AS backend
ARG SCHOLAR_GRAPH_REVISION=unknown
LABEL org.opencontainers.image.revision=${SCHOLAR_GRAPH_REVISION}
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/backend \
    PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SCHOLAR_GRAPH_DATA_DIR=/app/data/records SCHOLAR_GRAPH_QA_MODE=extractive \
    SCHOLAR_GRAPH_RETRIEVAL_MODE=lexical MPLCONFIGDIR=/app/data/matplotlib-cache \
    SCHOLAR_GRAPH_VECTOR_PYTHON=/opt/vector-venv/bin/python \
    SCHOLAR_GRAPH_BGE_M3_PATH=/app/data/module-four-models/bge-m3 \
    HOME=/app/data/home
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
       ca-certificates fonts-dejavu-core libatomic1 libgl1 libglib2.0-0 libgomp1 \
       libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/ ./backend/
COPY contracts/ ./contracts/
RUN --mount=type=cache,target=/root/.cache/pip \
    unset PIP_NO_CACHE_DIR \
    && python -m pip install --timeout 60 pip==26.2.2 \
    && python -m pip install './backend[ocr,test]' --timeout 60 --resume-retries 20 \
    && python -m pip check
COPY --from=vector-runtime /opt/vector-venv /opt/vector-venv
# Include independently built Node/TypeScript for the existing actual proxy test.
COPY --from=frontend-dependencies /usr/local/bin/node /usr/local/bin/node
COPY --from=frontend-build /app/frontend ./frontend/
COPY tests/ ./tests/
COPY Dockerfile docker-compose.yml .dockerignore README.md ./
COPY services/docker-compose.acceptance.yml ./services/docker-compose.acceptance.yml
RUN useradd --uid 1000 --create-home --home-dir /home/scholar scholar \
    && mkdir -p /app/data/home /app/tests/reports \
    && chown -R scholar:scholar /app/data /app/tests/reports
USER scholar
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "scholar_graph.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
