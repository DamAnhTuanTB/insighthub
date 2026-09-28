#!/usr/bin/env bash
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
PYTHON_BIN=${VERIFY_PYTHON:-$ROOT/.venv/bin/python}
BOT_URL=${BOT_URL:-http://127.0.0.1:18080}
BOT_PORT=${BOT_URL##*:}
BOT_PORT=${BOT_PORT%%/*}
RUN_DIR="$ROOT/tmp/day5"
mkdir -p "$RUN_DIR"

if [ ! -x "$PYTHON_BIN" ]; then
    printf '%s\n' "Missing Python environment: $PYTHON_BIN" >&2
    exit 2
fi

SIGNING_SECRET=$($PYTHON_BIN -c 'import secrets; print(secrets.token_hex(32))')
INSIGHTHUB_REPO_ROOT="$ROOT" \
SLACK_SIGNING_SECRET="$SIGNING_SECRET" \
CHATOPS_QUEUE_MODE=memory \
CHATOPS_TOOL_MODE=fixture \
PYTHONPATH="$ROOT/chatops-bot" \
    "$PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port "$BOT_PORT" \
    >"$RUN_DIR/bot.log" 2>&1 &
BOT_PID=$!
cleanup() {
    kill "$BOT_PID" 2>/dev/null || true
    wait "$BOT_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

attempt=0
until "$PYTHON_BIN" -c "import urllib.request; urllib.request.urlopen('$BOT_URL/healthz', timeout=1)" 2>/dev/null; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 30 ]; then
        printf '%s\n' 'ChatOps ingress did not become ready.' >&2
        exit 1
    fi
    sleep 0.2
done

cd "$ROOT"
INSIGHTHUB_REPO_ROOT="$ROOT" "$PYTHON_BIN" -B scripts/verify.py day5 \
    --evidence-dir evidence --bot-url "$BOT_URL" --bot-transport http
