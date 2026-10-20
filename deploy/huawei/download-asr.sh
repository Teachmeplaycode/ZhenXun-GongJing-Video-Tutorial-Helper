#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT/backend"
uv pip install --python .venv/bin/python \
  --index-url "${GONGJING_PYPI_INDEX:-https://repo.huaweicloud.com/repository/pypi/simple/}" modelscope
# Download converted weights and tokenizer files. Model repository code is not imported or executed.
.venv/bin/python -c 'from modelscope import snapshot_download; snapshot_download("pengzhendong/faster-whisper-small", local_dir="/root/runtime/gongjing/models/whisper-small")'
