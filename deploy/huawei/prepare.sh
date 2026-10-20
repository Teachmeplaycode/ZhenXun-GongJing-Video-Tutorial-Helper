#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
command -v ffmpeg >/dev/null || { echo '请先通过系统包管理器安装 ffmpeg（含 ffprobe）'; exit 1; }
INDEX="${GONGJING_PYPI_INDEX:-https://repo.huaweicloud.com/repository/pypi/simple/}"
cd "$PROJECT_ROOT/backend"
if command -v uv >/dev/null; then
  # [tool.uv] exclude-dependencies in pyproject.toml keeps rapidocr's opencv-python
  # (needs libGL, and collides with the project's opencv-python-headless, both shipping cv2)
  # out of the resolution; a clean `--extra cloud` install works without libGL.
  uv sync --python python3 --extra cloud --no-dev --system-certs --default-index "$INDEX"
else
  # Same resolution without uv, verified on a clean openEuler aarch64 without libGL (2026-10-20):
  # install the headless cv2 first, add rapidocr WITHOUT its dependencies so it cannot pull the
  # libGL opencv-python, then install its real remaining requirements explicitly.
  # Keep this list in sync with [project.dependencies] and the cloud extra in pyproject.toml.
  python3 -m venv .venv
  .venv/bin/pip install --index-url "$INDEX" --upgrade pip
  .venv/bin/pip install --index-url "$INDEX" --progress-bar off \
    fastapi 'uvicorn[standard]' httpx python-multipart trafilatura ddgs playwright segno \
    opencv-python-headless numpy 'markdown-it-py>=4,<5'
  .venv/bin/pip install --index-url "$INDEX" --progress-bar off 'faster-whisper>=1.2,<2' 'av>=14,<16'
  .venv/bin/pip install --index-url "$INDEX" --progress-bar off --no-deps 'rapidocr-onnxruntime>=1.4,<2'
  .venv/bin/pip install --index-url "$INDEX" --progress-bar off \
    onnxruntime numpy Pillow pyclipper PyYAML Shapely six tqdm
fi
cd "$PROJECT_ROOT/front"
npm ci --no-audit --no-fund
npm run build
