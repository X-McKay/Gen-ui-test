# AI Governance Intake — backend (FastAPI + ag_ui_adk + Google ADK).
#
#   docker build -t intake-backend backend
#   docker run --rm -p 8000:8000 --env-file .env -v intake-data:/data intake-backend
#
# WeasyPrint renders the PDF form, so the image carries pango/cairo and a font.
# git is needed for the shallow clones made by repository analysis.

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libffi-dev \
        libjpeg62-turbo \
        libopenjp2-7 \
        libcairo2 \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# uv, pinned. The lock file is the source of truth: --frozen never re-resolves.
COPY --from=ghcr.io/astral-sh/uv:0.11.12 /uv /uvx /bin/

WORKDIR /app

# Dependencies first so application edits do not invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Application code, the schema exporter and the fixture repositories used by MOCK_MODEL=1.
COPY app ./app
COPY scripts ./scripts
COPY tests/fixtures ./tests/fixtures
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Non-root user; /data holds the sqlite file (mount a volume there).
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin intake \
    && mkdir -p /data \
    && chown -R intake:intake /app /data
USER intake

ENV PATH="/app/.venv/bin:$PATH" \
    DATABASE_URL=sqlite:////data/intake.db

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
