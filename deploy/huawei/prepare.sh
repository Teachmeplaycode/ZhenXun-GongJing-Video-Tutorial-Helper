#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
command -v ffmpeg >/dev/null || { echo '请先通过系统包管理器安装 ffmpeg（含 ffprobe）'; exit 1; }
cd "$PROJECT_ROOT/backend"
uv sync --python python3 --extra cloud --no-dev --system-certs \
  --default-index "${GONGJING_PYPI_INDEX:-https://repo.huaweicloud.com/repository/pypi/simple/}"
cd "$PROJECT_ROOT/front"
npm ci --no-audit --no-fund
npm run build
