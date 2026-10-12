# API do estudo GTO (uso pessoal). Publique a porta só em localhost (research R16):
#   docker build -t gto-api .
#   docker run -p 127.0.0.1:8000:8000 -v gto-data:/data gto-api

# ---------- build: dependências + warm-up do Numba (grava o cache do JIT) ----------
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock .python-version ./
COPY engine/pyproject.toml engine/pyproject.toml
COPY api/pyproject.toml api/pyproject.toml
COPY engine/src engine/src
COPY api/src api/src
RUN uv sync --frozen --no-dev --all-packages --no-editable
ENV NUMBA_CACHE_DIR=/opt/numba-cache GTO_TABLES_DIR=/opt/numba-cache
RUN mkdir -p /opt/numba-cache && /app/.venv/bin/python -m gto_engine.warmup

# ---------- runtime ----------
FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 1000 gto && mkdir -p /data && chown gto /data
WORKDIR /app
COPY --from=build --chown=gto /app/.venv /app/.venv
COPY --from=build --chown=gto /opt/numba-cache /opt/numba-cache
ENV PATH=/app/.venv/bin:$PATH \
    NUMBA_CACHE_DIR=/opt/numba-cache \
    GTO_TABLES_DIR=/opt/numba-cache \
    GTO_DATA_DIR=/data \
    GTO_HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1
USER gto
VOLUME /data
EXPOSE 8000
# dentro do container escuta em 0.0.0.0; o isolamento vem de publicar só em 127.0.0.1
CMD ["uvicorn", "gto_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
