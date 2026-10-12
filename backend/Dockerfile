# The Tiki-Taka backend: FastAPI on uvicorn. The simulated matchday is baked in at build time, so
# a cold start (the app scales to zero) loads it in well under a second instead of simulating
# ten matches; the agents' cached runs ship with it, so a visit replays them instead of paying
# for them again. Built in Azure (az acr build), no local Docker needed.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    MATCHDAY_CACHE_DIR=/app/.cache/matchday \
    MATCHDESK_AGENT_CACHE=/app/.cache/agent-runs \
    MATCH_START_MINUTE=55

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY .cache/agent-runs ./.cache/agent-runs
RUN python -m app.generator.matchday

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "3"]
