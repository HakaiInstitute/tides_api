FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

EXPOSE 80

ADD . /app

WORKDIR /app

# Install the project's dependencies using the lockfile and settings
RUN uv sync --locked --no-install-project --no-dev

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

CMD ["uvicorn", "tide_api.main:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "80"]
