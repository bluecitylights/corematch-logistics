FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Install dependencies into the system Python (no venv needed in a container)
COPY pyproject.toml uv.lock ./
RUN uv pip install --system --no-cache \
    duckdb \
    "fastapi" \
    "uvicorn[standard]" \
    jinja2 \
    pandas \
    pyroaring \
    python-multipart

# Copy application source
COPY . .

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
