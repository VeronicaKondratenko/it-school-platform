#!/usr/bin/env bash
set -euo pipefail

echo "=================================================="
echo "  IT School Platform - SETUP + SEED + START"
echo "  Creates venv, installs deps, fills the database"
echo "  with realistic data, then launches the system."
echo "=================================================="
echo

cd "$(dirname "$0")"

echo "[1/7] Checking Python..."
if command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_CMD="python"
else
  echo "[ERROR] Python was not found in PATH. Install Python 3.10+ and retry."; exit 1
fi

echo "[2/7] Checking virtual environment (.venv)..."
if [ ! -f ".venv/bin/python" ]; then
  echo "Creating .venv..."
  "$PYTHON_CMD" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[3/7] Installing dependencies..."
python -m pip install --upgrade pip
pip install -r backend/requirements.txt

echo "[4/7] Checking backend/.env ..."
if [ ! -f "backend/.env" ]; then
  echo "backend/.env was not found. Creating it from backend/.env.example..."
  cp "backend/.env.example" "backend/.env"
  echo
  echo "[ACTION REQUIRED] Edit backend/.env and set a valid DATABASE_URL (PostgreSQL"
  echo "must be running and the database must exist), plus SECRET_KEY. Then re-run this script."
  exit 1
fi

echo "[5/7] Applying Alembic migrations (base tables)..."
alembic -c backend/alembic.ini upgrade head || echo "(Alembic error ignored - the seed step creates any missing tables.)"

echo "[6/7] Seeding REALISTIC data..."
echo "WARNING: this DELETES all existing courses and users EXCEPT the test accounts"
echo "(admin@school.com, teacher@example.com, student@example.com)."
python -m backend.seed_realistic

echo "[7/7] Starting backend + frontend and opening browser..."

fail() { echo; echo "Setup/startup failed. Check messages above."; exit 1; }

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
echo "Setup + seed + startup complete."
echo "Account table: backend/accounts.csv (all passwords = password)"
echo "Press Ctrl+C to stop both services."
wait "$BACKEND_PID" "$FRONTEND_PID"
