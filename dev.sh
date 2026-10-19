#!/usr/bin/env bash
# Start GongJ!ng? for development: checks the environment, installs what is missing, then runs the
# backend (uvicorn --reload on :8000) and the frontend (Vite on :5173) with their logs in one terminal.
#
#   ./dev.sh          check, then start both; Ctrl+C stops both
#   ./dev.sh --check  only check
#   API_PORT=8011 WEB_PORT=5191 GONGJING_DATA_DIR=/tmp/x ./dev.sh   a second, separate copy
#
# Written for the macOS system bash (3.2): no associative arrays or other bash 4 features.
set -u

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONT="$ROOT/front"
ENV_FILE="$BACKEND/.env"
ACCOUNTS_FILE="$BACKEND/.env.accounts"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"
export API_PORT WEB_PORT
OLLAMA_URL="${DECISION_URL:-http://localhost:11434}"

if [ -t 1 ]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; CYAN=$'\033[36m'; RESET=$'\033[0m'
else
  BOLD=; DIM=; RED=; GREEN=; YELLOW=; CYAN=; RESET=
fi
ok()   { printf '  %s✓%s %s\n' "$GREEN" "$RESET" "$1"; }
warn() { printf '  %s!%s %s\n' "$YELLOW" "$RESET" "$1"; WARNINGS=$((WARNINGS + 1)); }
fail() { printf '  %s✗%s %s\n' "$RED" "$RESET" "$1"; FAILURES=$((FAILURES + 1)); }
FAILURES=0
WARNINGS=0

# Value of NAME in backend/.env, or in the environment (which wins, as in the backend).
setting() {
  local name="$1" value=""
  eval "value=\${$name:-}"
  # Logins saved from the page (.env.accounts) win over .env, as in the backend.
  local file
  for file in "$ACCOUNTS_FILE" "$ENV_FILE"; do
    if [ -z "$value" ] && [ -f "$file" ]; then
      value="$(grep -E "^[[:space:]]*(export[[:space:]]+)?$name=" "$file" | tail -1 | sed -E 's/^[^=]*=//; s/^["'\'']//; s/["'\'']$//')"
    fi
  done
  printf '%s' "$value"
}
has_setting() { [ -n "$(setting "$1")" ]; }

check_tools() {
  printf '%s工具%s\n' "$BOLD" "$RESET"
  if command -v uv >/dev/null 2>&1; then ok "uv $(uv --version 2>/dev/null | awk '{print $2}')"; else fail "没有 uv：brew install uv"; fi
  if command -v node >/dev/null 2>&1; then ok "node $(node -v)"; else fail "没有 Node.js：brew install node"; fi
  if command -v ffmpeg >/dev/null 2>&1; then ok "ffmpeg"; else fail "没有 ffmpeg（抽帧和转写都要用）：brew install ffmpeg"; fi
  # Optional: other platforms' links (抖音、YouTube、小红书 …) through alcedo (backend/modules/video_source/alcedo.py).
  local alcedo
  alcedo="$(setting ALCEDO_BIN)"
  [ -z "$alcedo" ] && alcedo="$(command -v alcedo 2>/dev/null || true)"
  [ -z "$alcedo" ] && alcedo="$(ls "$(dirname "$ROOT")"/tools/alcedo-*/alcedo-cli-*/bin/alcedo 2>/dev/null | tail -1)"
  if [ -n "$(setting ALCEDO_URL)" ]; then ok "alcedo 服务 $(setting ALCEDO_URL)"
  elif [ -n "$alcedo" ] && [ -x "$alcedo" ]; then ok "$("$alcedo" --version 2>/dev/null)（抖音、YouTube 等链接）"
  else warn "没有 alcedo：只能解析 B 站和视频号链接（./scripts/install-alcedo.sh 可装上抖音、YouTube 等 35 个平台）"; fi
}

check_env() {
  printf '%s配置（backend/.env）%s\n' "$BOLD" "$RESET"
  if [ ! -f "$ENV_FILE" ]; then
    fail "没有 backend/.env：至少写一行 DEEPSEEK_API_KEY=sk-…，或 LLM_PROVIDER=ollama"
    return
  fi
  local provider; provider="$(setting LLM_PROVIDER)"
  if [ "$provider" = "ollama" ]; then
    ok "问答模型：本地 Ollama（$(setting LLM_MODEL)）"
  elif has_setting DEEPSEEK_API_KEY || has_setting LLM_API_KEY || has_setting LLM_KEY_FILE; then
    ok "问答模型：DeepSeek / OpenAI 兼容服务（已配置 key）"
  else
    fail "没有问答模型的 key：写 DEEPSEEK_API_KEY=…，或 LLM_PROVIDER=ollama 改用本地模型"
  fi
  if has_setting DEEPSEEK_API_KEY; then ok "联网搜索：DeepSeek 搜索（带权威度）"; fi
  if has_setting TAVILY_API_KEY || has_setting Tavily_API_KEY; then ok "联网搜索备用：Tavily"; fi
  if has_setting OPENALEX_API_KEY; then ok "论文检索：OpenAlex（带 key，约 1000 次/天）"; else warn "没有 OPENALEX_API_KEY：论文检索每天约 100 次（openalex.org 免费注册）"; fi
  if has_setting BILIBILI_COOKIE; then ok "B 站评论：已配置登录 Cookie"; else warn "没有登录 B 站：评论只能读前 3 条热门（弹幕不受影响）；启动后在页面右上角「账号」扫码登录"; fi
  if has_setting YUANBAO_COOKIE; then ok "视频号：已登录腾讯元宝（过期后在页面「账号」里重新扫码）"; else warn "没有登录腾讯元宝：视频号链接解析不了；启动后在页面右上角「账号」用微信扫码登录"; fi
}

check_ollama() {
  printf '%s本地模型（Ollama）%s\n' "$BOLD" "$RESET"
  local decision; decision="$(setting DECISION)"
  local model; model="$(setting DECISION_MODEL)"; model="${model:-qwen3.5:9b}"
  if [ "$decision" = "off" ] && [ "$(setting LLM_PROVIDER)" != "ollama" ]; then
    ok "决策模块已关闭（DECISION=off），不需要 Ollama"
    return
  fi
  if ! curl -s -m 2 "$OLLAMA_URL/api/version" >/dev/null 2>&1; then
    if [ "$(setting LLM_PROVIDER)" = "ollama" ]; then
      fail "Ollama 没有运行（问答用的是本地模型）：打开 Ollama 应用，或运行 ollama serve"
    else
      warn "Ollama 没有运行：决策模块（过滤搜索结果、拦截注入、判断是否查资料）会退回简单规则"
    fi
    return
  fi
  ok "Ollama $(curl -s -m 2 "$OLLAMA_URL/api/version" | sed -E 's/.*"version":"([^"]*)".*/\1/')"
  if curl -s -m 3 "$OLLAMA_URL/api/tags" | grep -q "\"name\":\"$model\""; then
    ok "决策模型 $model"
  else
    warn "Ollama 里没有 ${model}：ollama pull $model"
  fi
}

port_owner() { lsof -t -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | head -1; }

# A port held by this project's own server (an older run) is freed on start, so the newest code runs;
# anything else on it is left alone and reported.
check_port() {
  local port="$1" what="$2" ours="$3"
  local pid; pid="$(port_owner "$port")"
  if [ -z "$pid" ]; then
    ok "$what $port 空闲"
    return
  fi
  local cmd; cmd="$(ps -o command= -p "$pid" 2>/dev/null)"
  local since; since="$(ps -o lstart= -p "$pid" 2>/dev/null | sed -E 's/  +/ /g; s/^ //; s/ $//')"
  if printf '%s' "$cmd" | grep -q -- "$ours"; then
    STALE_PIDS="$STALE_PIDS $pid"
    warn "$what $port 上还跑着之前启动的进程（PID ${pid}，启动于 ${since}），启动时会先停掉它，确保运行的是最新代码"
  else
    fail "$what $port 被其他程序占用（PID ${pid}：$(printf '%s' "$cmd" | cut -c1-70)），请先关掉它或换端口"
  fi
}

check_ports() {
  printf '%s端口%s\n' "$BOLD" "$RESET"
  check_port "$API_PORT" "后端" "uvicorn app:app"
  check_port "$WEB_PORT" "前端" "$FRONT/node_modules/.bin/vite"
}

install_deps() {
  printf '%s依赖%s\n' "$BOLD" "$RESET"
  if (cd "$BACKEND" && uv sync --quiet); then ok "后端依赖（uv sync）"; else fail "uv sync 失败"; return 1; fi
  if [ "$(setting BROWSER)" != "off" ]; then
    local shell_dir
    shell_dir=$(cd "$BACKEND" && uv run --quiet playwright install --dry-run --only-shell chromium 2>/dev/null | awk '/Install location/ {print $3; exit}')
    if [ -n "$shell_dir" ] && [ -d "$shell_dir" ]; then ok "浏览器操作：无头 Chromium 已下载"
    else warn "浏览器操作要用的 Chromium 还没下载（约 100 MB）：cd backend && uv run playwright install --only-shell chromium"; fi
  fi
  if [ ! -d "$FRONT/node_modules" ] || [ "$FRONT/package-lock.json" -nt "$FRONT/node_modules/.package-lock.json" ]; then
    if (cd "$FRONT" && npm install --silent); then ok "前端依赖（npm install）"; else fail "npm install 失败"; return 1; fi
  else
    ok "前端依赖已是最新"
  fi
}

# Prefix each line of a stream, so the two servers' logs can share one terminal.
prefix() { local tag="$1"; while IFS= read -r line; do printf '%s %s\n' "$tag" "$line"; done; }

STALE_PIDS=""
printf '\n%sGongJ!ng? 开发环境检查%s\n' "$BOLD" "$RESET"
check_tools
check_env
check_ollama
check_ports
printf '\n'
if [ "$FAILURES" -gt 0 ]; then
  printf '%s%d 项必须先处理%s（另有 %d 项提示），处理后再运行 ./dev.sh\n' "$RED" "$FAILURES" "$RESET" "$WARNINGS"
  exit 1
fi
if [ "${1:-}" = "--check" ]; then
  printf '%s检查通过%s（%d 项提示）\n' "$GREEN" "$RESET" "$WARNINGS"
  exit 0
fi

install_deps || exit 1

for pid in $STALE_PIDS; do
  kill "$pid" 2>/dev/null
  ok "已停掉之前的进程（PID ${pid}）"
done
for _ in 1 2 3 4 5 6 7 8 9 10; do
  [ -z "$(port_owner "$API_PORT")" ] && [ -z "$(port_owner "$WEB_PORT")" ] && break
  sleep 0.3
done

PIDS=""
cleanup() {
  trap - INT TERM EXIT
  printf '\n%s正在停止…%s\n' "$DIM" "$RESET"
  for pid in $PIDS; do kill "$pid" 2>/dev/null; done
  # uvicorn --reload and vite each run child processes: stop the process groups' leftovers too —
  # only this copy's (by port), so a second copy on other ports leaves the main one running.
  pkill -f "uvicorn app:app --port $API_PORT" 2>/dev/null
  local web; web="$(port_owner "$WEB_PORT")"
  [ -n "$web" ] && kill "$web" 2>/dev/null
  wait 2>/dev/null
  exit 0
}
trap cleanup INT TERM EXIT

# --reload-include .env: edited keys take effect without restarting by hand.
(cd "$BACKEND" && exec uv run uvicorn app:app --port "$API_PORT" --reload --reload-include .env 2>&1) | prefix "${CYAN}[api]${RESET}" &
PIDS="$PIDS $!"
(cd "$FRONT" && exec npm run dev --silent 2>&1) | prefix "${GREEN}[web]${RESET}" &
PIDS="$PIDS $!"

for _ in $(seq 1 60); do curl -s -m 1 "http://127.0.0.1:$API_PORT/api/health" >/dev/null 2>&1 && break; sleep 0.5; done
printf '\n%s就绪%s  打开 %shttp://localhost:%s%s  （后端 http://localhost:%s；改代码或 .env 会自动重载；Ctrl+C 停止）\n\n' \
  "$BOLD" "$RESET" "$BOLD" "$WEB_PORT" "$RESET" "$API_PORT"
wait
