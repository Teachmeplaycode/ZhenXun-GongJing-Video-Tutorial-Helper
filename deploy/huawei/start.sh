#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export GONGJING_DATA_DIR="${GONGJING_DATA_DIR:-/root/gongjing-data}"
export ASR_BACKEND="${ASR_BACKEND:-faster-whisper}"
export ASR_MODEL="${ASR_MODEL:-small}"
export ASR_CPU_THREADS="${ASR_CPU_THREADS:-4}"
export OCR_BACKEND="${OCR_BACKEND:-rapidocr}"
export DECISION="${DECISION:-off}"
export BROWSER="${BROWSER:-off}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-2}"
cd "$PROJECT_ROOT/backend"
exec .venv/bin/uvicorn cloud_app:app --host "${BIND_HOST:-0.0.0.0}" --port "${PORT:-17080}"
