FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

EXPOSE 80

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

COPY ./tide_api /app/tide_api

CMD ["uvicorn", "tide_api.main:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "80"]
