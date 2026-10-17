# Production image: the React build served by the FastAPI app on one port.
# Build: docker build -t marketpulse .   Run: see docs/deployment.md

FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ENVIRONMENT=production STATIC_DIR=/app/static
WORKDIR /app
RUN useradd --create-home --uid 10001 marketpulse
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY --from=web /web/dist ./static
COPY deploy/start.sh ./start.sh
USER marketpulse
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/api/health', timeout=4)"
CMD ["./start.sh"]
