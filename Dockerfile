# Stage 1: build the React dashboard
FROM node:22-slim AS frontend
WORKDIR /app/src/frontend
COPY src/frontend/package.json src/frontend/package-lock.json ./
RUN npm ci
COPY src/frontend/ ./
RUN npm run build

# Stage 2: Python API that also serves the built dashboard
# (same folder layout as the repo, so the API finds src/frontend/dist)
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/backend/ src/backend/
COPY --from=frontend /app/src/frontend/dist src/frontend/dist

WORKDIR /app/src/backend
# Build the demo database into the image (~5 s)
RUN python -m portfolio.seed

# No Redis server on the free plan: use the in-memory fake by default.
# Point REDIS_URL at a real Redis (e.g. Render Key Value) to use one.
ENV REDIS_URL=memory://
EXPOSE 8000
CMD ["sh", "-c", "uvicorn portfolio.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
