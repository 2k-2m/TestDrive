#!/usr/bin/env bash
set -euo pipefail

### ANDROID_SDK EXPLICIT EXPORT (para Appium en systemd)
export ANDROID_SDK_ROOT=/home/jetson/Android/Sdk
export ANDROID_HOME=/home/jetson/Android/Sdk
export PATH="/usr/local/bin:/usr/bin:/bin:$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/tools:$ANDROID_SDK_ROOT/tools/bin:$ANDROID_SDK_ROOT/emulator:$PATH"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
cd "$SCRIPT_DIR"

# VENV antiguo (ruta con espacio)
PYBIN="/home/jetson/Desktop/Split Llamadas/.venv/bin/python"
PIDS_FILE="$SCRIPT_DIR/.run_pids"

# === SCRIPTS ===
SCRIPT_WHATS="$SCRIPT_DIR/Whats/llamada_CSV_Split_Viva.py"   # se mantiene
SCRIPT_G1="$SCRIPT_DIR/G-net/G-track.py"                     # reemplaza al Chrome
SCRIPT_G2="$SCRIPT_DIR/G-net/G-track2.py"                    # se mantiene

# === APPIUM PUERTOS ===
PORT_WHATS=4723
PORT_G1=4730   # slot antes usado por Chrome → ahora G-track.py
PORT_G2=4786

# Base path por puerto (todo vacío)
declare -A BASE_PATHS=(
  ["$PORT_WHATS"]=""
  ["$PORT_G1"]=""
  ["$PORT_G2"]=""
)

# Flags extra por puerto (sin allow-insecure ni base-path)
declare -A EXTRA_FLAGS=()  # vacío intencionalmente

# UDIDs requeridos (Whats, G-track, G-track2)
# Nota: Ajusta aquí si cambian los equipos físicos.
REQUIRED_UDIDS=("6NUDU18529000033" "6NU7N18614004267" "6NU7N18614005207")

# PATH + nvm (para appium/npx)
if [[ -s "/home/jetson/.nvm/nvm.sh" ]]; then . "/home/jetson/.nvm/nvm.sh"; fi

need(){ command -v "$1" >/dev/null 2>&1 || { echo "[ERROR] Falta '$1' en PATH"; exit 1; }; }
need adb; need curl
[[ -x "$PYBIN" ]] || { echo "[ERROR] No existe venv en $PYBIN"; exit 1; }
for f in "$SCRIPT_WHATS" "$SCRIPT_G1" "$SCRIPT_G2"; do [[ -f "$f" ]] || { echo "[ERROR] Falta script: $f"; exit 1; }; done

# Detectar appium
if command -v appium >/dev/null 2>&1; then APPIUM_CMD=(appium)
elif command -v npx >/dev/null 2>&1; then APPIUM_CMD=(npx appium)
else echo "[ERROR] No encuentro 'appium' ni 'npx'"; exit 1; fi

: > "$PIDS_FILE"

start_appium(){
  local port="$1"
  local args=(--relaxed-security -p "$port")   # solo relaxed-security
  nohup "${APPIUM_CMD[@]}" "${args[@]}" >"$HOME/appium-${port}.log" 2>&1 &
  echo $! >> "$PIDS_FILE"
  echo "[INFO] Appium ${port} lanzado. Log: $HOME/appium-${port}.log"
}

wait_appium(){
  local port="$1"
  local url="http://127.0.0.1:${port}/status"
  for _ in {1..45}; do
    curl -sf "$url" >/dev/null 2>&1 && { echo "[OK] Appium ${port} listo"; return 0; }
    sleep 1
  done
  echo "[WARN] Appium ${port} no respondió aún en ${url}; sigo."
  return 0
}

have_all_devices(){
  local out; out="$(adb devices 2>/dev/null || true)"
  for udid in "${REQUIRED_UDIDS[@]}"; do
    grep -qE "^${udid}[[:space:]]+device" <<<"$out" || return 1
  done
  return 0
}

echo "[INFO] Esperando a que estén conectados los 3 dispositivos: ${REQUIRED_UDIDS[*]}"
for ((i=1;i<=180;i++)); do have_all_devices && { echo "[OK] Los 3 dispositivos están en 'device'."; break; }; sleep 1; done
have_all_devices || echo "[WARN] Aún faltan dispositivos, se reintentará en bucle."

# Bucle principal (reintentos no fatales)
while true; do
  if have_all_devices; then
    echo "[INFO] Iniciando Appium..."
    for p in "$PORT_WHATS" "$PORT_G1" "$PORT_G2"; do start_appium "$p"; done
    for p in "$PORT_WHATS" "$PORT_G1" "$PORT_G2"; do wait_appium "$p"; done

    echo "[INFO] Ejecutando scripts..."
    "$PYBIN" "$SCRIPT_WHATS"  & echo $! >> "$PIDS_FILE"
    "$PYBIN" "$SCRIPT_G1"     & echo $! >> "$PIDS_FILE"   # G-track.py en 4730
    "$PYBIN" "$SCRIPT_G2"     & echo $! >> "$PIDS_FILE"

    echo "[OK] Lanzados. Monitoreando..."
    while true; do
      sleep 10
      mapfile -t PIDS < <(grep -E '^[0-9]+$' "$PIDS_FILE" || true)
      alive=0; for pid in "${PIDS[@]:-}"; do kill -0 "$pid" 2>/dev/null && alive=1; done
      [[ $alive -eq 1 ]] || { echo "[WARN] No quedan procesos vivos; reiniciando ciclo…"; break; }
    done

    : > "$PIDS_FILE"
    fuser -k ${PORT_WHATS}/tcp ${PORT_G1}/tcp ${PORT_G2}/tcp 2>/dev/null || true
    pkill -f 'appium --relaxed-security' 2>/dev/null || true
    pkill -f 'npx appium' 2>/dev/null || true
  else
    echo "[INFO] Aún no están los 3 dispositivos. Reintentando en 15s…"
    sleep 15
  fi
done

trap 'echo "[SIG] stop_finale.sh"; "$SCRIPT_DIR/stop_finale.sh"; exit 0' INT TERM
