#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT/backend"
INDEX="${GONGJING_PYPI_INDEX:-https://repo.huaweicloud.com/repository/pypi/simple/}"
if command -v uv >/dev/null; then
  uv pip install --python .venv/bin/python --index-url "$INDEX" modelscope
else
  .venv/bin/python -m pip install --index-url "$INDEX" modelscope
fi
# Download converted weights and tokenizer files. Model repository code is not imported or executed.
.venv/bin/python -c 'from modelscope import snapshot_download; snapshot_download("pengzhendong/faster-whisper-small", local_dir="/root/runtime/gongjing/models/whisper-small")'
