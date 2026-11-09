# ---------- Builder ----------
FROM python:3.12-slim AS builder
WORKDIR /app
# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc build-essential && rm -rf /var/lib/apt/lists/*
COPY backend/pyproject.toml backend/poetry.lock ./
# Install Poetry and project dependencies (no dev packages)
RUN pip install --upgrade pip && pip install poetry && poetry install --no-root --only main
# ---------- Runtime ----------
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app /app
COPY backend/app ./app
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]