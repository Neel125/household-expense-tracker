# Ledger & Card — one image, one process: FastAPI serves the API *and* the
# compiled React app (see the static mount in backend/app/main.py).

# ---------------------------------------------------------- build the frontend
FROM node:20-alpine AS frontend
WORKDIR /app/frontend

# Deps first, so a source-only change doesn't re-download node_modules.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# No VITE_API_URL: the backend serves these files, so /api is same-origin.
RUN npm run build

# ------------------------------------------------------------------- runtime
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DATABASE_URL=sqlite:////app/data/expense_tracker.db

WORKDIR /app/backend

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
# app/main.py looks for ../../frontend/dist relative to itself -> /app/frontend/dist.
COPY --from=frontend /app/frontend/dist /app/frontend/dist
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# The SQLite file lives on a volume so it survives `docker compose down`.
# Owned by the app user: Docker copies this ownership onto a fresh volume.
RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
 && useradd --create-home --uid 10001 app \
 && mkdir -p /app/data \
 && chown -R app:app /app/data
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["sh", "-c", "python -c \"import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/api/health').read()\""]

ENTRYPOINT ["docker-entrypoint.sh"]
