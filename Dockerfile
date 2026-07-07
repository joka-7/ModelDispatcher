# syntax=docker/dockerfile:1

# --------------------------------------------------------------------------- #
# Stage 1 — build the React SPA
# --------------------------------------------------------------------------- #
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY demo/frontend/package.json demo/frontend/package-lock.json ./
RUN npm ci
COPY demo/frontend/ ./
RUN npm run build

# --------------------------------------------------------------------------- #
# Stage 2 — Python runtime serving the API + built SPA
# --------------------------------------------------------------------------- #
FROM python:3.13-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MD_STATIC_DIR=/app/demo/backend/static

# Install the gateway library first (its own layer, changes rarely).
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .

# Backend service dependencies.
COPY demo/backend ./demo/backend
RUN pip install --no-cache-dir -r demo/backend/requirements.txt

# Copy the compiled SPA into the location FastAPI serves from.
COPY --from=frontend /app/frontend/dist ./demo/backend/static

EXPOSE 8000
CMD ["uvicorn", "app:app", "--app-dir", "demo/backend", "--host", "0.0.0.0", "--port", "8000"]
