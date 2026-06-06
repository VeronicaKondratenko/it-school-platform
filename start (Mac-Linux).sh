#!/usr/bin/env bash
set -euo pipefail

echo "============================================="
echo "  IT School Platform - Start (RUN ONLY)"
echo "  (does NOT install or seed; setup must be done already)"
echo "============================================="
echo

cd "$(dirname "$0")"

if [ ! -f ".venv/bin/python" ]; then
  echo "[ERROR] Virtual environment .venv was not found."
  echo "Run ./\"setup-and-start (Mac-Linux).sh\" first to install and seed the project."
  exit 1
fi

echo "Activating .venv..."
# shellcheck disable=SC1091
source .venv/bin/activate

echo "Starting backend + frontend and opening browser..."

fail() { echo; echo "Startup failed. Check messages above."; exit 1; }

is_port_busy() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN -n -P >/dev/null 2>&1; return $?
  fi
  if command -v ss >/dev/null 2>&1; then
    ss -ltn | awk '{print $4}' | grep -qE "(^|:)$port$"; return $?
  fi
  return 1
}

wait_for_port() {
  local port="$1"; local max_wait="$2"; local elapsed=0
  while (( elapsed < max_wait )); do
    if is_port_busy "$port"; then return 0; fi
    sleep 1; ((elapsed += 1))
  done
  return 1
}

FRONTEND_PORT=""
for candidate in 8080 8081 8082; do
  if ! is_port_busy "$candidate"; then FRONTEND_PORT="$candidate"; break; fi
done
if [[ -z "$FRONTEND_PORT" ]]; then
  echo "[ERROR] Frontend ports 8080, 8081 and 8082 are busy."; exit 1
fi
echo "Using frontend port: $FRONTEND_PORT"

cleanup() {
  echo; echo "Stopping services..."
  [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
if ! wait_for_port 8000 90; then echo "[ERROR] Backend did not open port 8000 in time."; fail; fi

python -m http.server "$FRONTEND_PORT" --directory frontend &
FRONTEND_PID=$!
if ! wait_for_port "$FRONTEND_PORT" 20; then echo "[ERROR] Frontend did not open port $FRONTEND_PORT in time."; fail; fi

if command -v open >/dev/null 2>&1; then
  open "http://localhost:$FRONTEND_PORT/index.html"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://localhost:$FRONTEND_PORT/index.html" >/dev/null 2>&1 || true
else
  echo "Open browser manually: http://localhost:$FRONTEND_PORT/index.html"
fi

echo
echo "Startup complete. Press Ctrl+C to stop both services."
wait "$BACKEND_PID" "$FRONTEND_PID"
