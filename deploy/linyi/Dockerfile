# 帧见 as one container: the built page and the API on port 8000, data in /data.
# Built from the repository root: docker compose -f deploy/linyi/compose.yaml build
FROM node:22-slim AS web
WORKDIR /src/front
COPY front/package.json front/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY front/ ./
ARG BASE_PATH=/GongJing
RUN VITE_BASE="${BASE_PATH}/" VITE_API_BASE="${BASE_PATH}" npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /usr/local/bin/uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --extra cloud --no-dev
COPY backend/ ./
COPY --from=web /src/front/dist /app/front/dist
ARG BASE_PATH=/GongJing
ENV GONGJING_DATA_DIR=/data HF_HOME=/data/models PUBLIC_DEMO=1 PUBLIC_PATH=${BASE_PATH} \
    ASR_BACKEND=faster-whisper ASR_MODEL=small ASR_CPU_THREADS=3 OCR_BACKEND=rapidocr \
    DECISION=off BROWSER=off OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"
CMD [".venv/bin/uvicorn", "cloud_app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--timeout-graceful-shutdown", "5"]
