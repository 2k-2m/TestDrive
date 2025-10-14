#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PIDS_FILE="$SCRIPT_DIR/.run_pids"

echo "[INFO] Deteniendo por $PIDS_FILE…"
if [[ -f "$PIDS_FILE" ]]; then
  mapfile -t PIDS < <(grep -E '^[0-9]+$' "$PIDS_FILE" || true)
  if [[ ${#PIDS[@]} -gt 0 ]]; then
    echo "[INFO] PIDs: ${PIDS[*]}"
    for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
    sleep 1
    for pid in "${PIDS[@]}"; do kill -0 "$pid" 2>/dev/null && { echo "[WARN] SIGKILL a $pid"; kill -9 "$pid" 2>/dev/null || true; }; done
  fi
  : > "$PIDS_FILE"
else
  echo "[WARN] No existe $PIDS_FILE; usando fallback…"
fi

echo "[INFO] Cerrando Appium (4723/4730/4786)…"
fuser -k 4723/tcp 4730/tcp 4786/tcp 2>/dev/null || true
pkill -f 'appium --relaxed-security' 2>/dev/null || true
pkill -f 'npx appium' 2>/dev/null || true

echo "[INFO] Matando posibles scripts residuales…"
pkill -f '/Finale_Alva/Whats/'                2>/dev/null || true
pkill -f '/Finale_Alva/Chrome/Chrome_FB_IG.py' 2>/dev/null || true
pkill -f '/Finale_Alva/G-net/G-track2.py'      2>/dev/null || true

echo "[OK] Todo detenido."
