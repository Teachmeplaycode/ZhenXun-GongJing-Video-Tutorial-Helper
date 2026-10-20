#!/usr/bin/env bash
set -euo pipefail
# Paste this script into the platform's bwrap environment startup editor.
# Extra read/write mount: /root/workspace/gongjing
export GONGJING_DATA_DIR=/root/runtime/gongjing/data
export HF_HOME=/root/runtime/gongjing/cache/huggingface
export XDG_CACHE_HOME=/root/runtime/gongjing/cache
export ASR_MODEL=/root/runtime/gongjing/models/whisper-small
export PORT=17080
exec /bin/bash /root/workspace/gongjing/deploy/huawei/start.sh
