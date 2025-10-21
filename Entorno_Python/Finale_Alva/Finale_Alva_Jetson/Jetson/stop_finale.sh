#!/usr/bin/env bash
set -euo pipefail
source /home/jetson/.finale_env.sh

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PIDS_FILE="$SCRIPT_DIR/.run_pids"

# Flags/paths
WHATS_DIR="$SCRIPT_DIR/Whats"
STOP_FLAG="$WHATS_DIR/stop.flag"
STOP_ALL="$SCRIPT_DIR/.stop_all"      # <- Señal global para autostart

# Dispositivo y puertos
DEVICE_WHATS="6NUDU18529000033"
APPIUM_PORTS=(4723 4730 4786)

# Tiempos (puedes override con /etc/systemd/system/finale.env)
T_INT="${T_INT:-20}"            # espera tras SIGINT (para que Python toque menús)
T_TERM="${T_TERM:-10}"          # espera tras SIGTERM
PAUSA_ENTRE_PULSOS="${PAUSA_ENTRE_PULSOS:-2}"

ts(){ date +"[%F %T]"; }

# ---- Appium helpers (cerrar SESIONES) ----
list_sessions(){
  local port="$1"
  curl -sf --max-time 2 "http://127.0.0.1:${port}/sessions" 2>/dev/null \
    | grep -oE '"id"\s*:\s*"[^"]+"' \
    | sed -E 's/.*"id"\s*:\s*"([^"]+)".*/\1/' || true
}
close_sessions(){
  local port="$1"
  echo "$(ts) [INFO] Cerrando sesiones Appium en $port…"
  local sid
  for sid in $(list_sessions "$port"); do
    curl -s -X DELETE "http://127.0.0.1:${port}/session/${sid}" >/dev/null 2>&1 || true
    sleep 0.2
  done
}

# ---- Señales a PIDs (SOLO scripts Python) ----
sig_pids(){
  local sig="$1"; shift
  local p
  for p in "$@"; do
    [[ -n "$p" ]] || continue
    if kill -0 "$p" 2>/dev/null; then
      local cmd="$(tr '\0' ' ' </proc/${p}/cmdline 2>/dev/null || true)"
      echo "$(ts) [SIG] ${sig} -> PID ${p}  ${cmd}"
      kill "-$sig" "$p" 2>/dev/null || true
    fi
  done
}
any_alive(){ for p in "$@"; do kill -0 "$p" 2>/dev/null && return 0; done; return 1; }
wait_until_dead(){
  local seconds="$1"; shift
  local end=$((SECONDS + seconds))
  while (( SECONDS < end )); do any_alive "$@" || return 0; sleep 1; done
  return 1
}

# 1) Señales “suaves” para Whats y autostart
echo "$(ts) [INFO] Creando stop.flag para Whats en: $STOP_FLAG"
mkdir -p "$WHATS_DIR" || true
: > "$STOP_FLAG" || true

echo "$(ts) [INFO] Creando .stop_all para autostart"
: > "$STOP_ALL" || true

# 2) Recolecta PIDs y FILTRA solo scripts Python (evita appium/node)
RAW_PIDS=()
if [[ -f "$PIDS_FILE" ]]; then
  mapfile -t RAW_PIDS < <(grep -E '^[0-9]+$' "$PIDS_FILE" || true)
fi

FILTERED_PIDS=()
if [[ "${#RAW_PIDS[@]}" -gt 0 ]]; then
  echo "$(ts) [INFO] PIDs en ejecución (sin filtrar): ${RAW_PIDS[*]}"
  for pid in "${RAW_PIDS[@]}"; do
    cmd="$(tr '\0' ' ' </proc/${pid}/cmdline 2>/dev/null || echo '')"
    if [[ "$cmd" == *"/python"* ]] && \
       { [[ "$cmd" == *"/G-net/G-track.py"* ]] || \
         [[ "$cmd" == *"/G-net/G-track2.py"* ]] || \
         [[ "$cmd" == *"/Whats/llamada_CSV_Split_Viva.py"* ]]; }; then
      FILTERED_PIDS+=("$pid")
      echo "$(ts) [INFO] Mantengo PID (script): $pid  $cmd"
    else
      echo "$(ts) [INFO] Omito PID (no script): $pid  $cmd"
    fi
  done
fi

# 3) Señal a scripts (Ctrl+C x2) y espera amplia
if [[ "${#FILTERED_PIDS[@]}" -gt 0 ]]; then
  echo "$(ts) [STEP] SIGINT pulso #1 a scripts"
  sig_pids INT "${FILTERED_PIDS[@]}"
  sleep "$PAUSA_ENTRE_PULSOS"
  echo "$(ts) [STEP] SIGINT pulso #2 a scripts"
  sig_pids INT "${FILTERED_PIDS[@]}"

  if wait_until_dead "$T_INT" "${FILTERED_PIDS[@]}"; then
    echo "$(ts) [OK] Scripts terminaron con SIGINT"
  else
    echo "$(ts) [WARN] Aún hay scripts tras SIGINT → SIGTERM"
    sig_pids TERM "${FILTERED_PIDS[@]}"
    if wait_until_dead "$T_TERM" "${FILTERED_PIDS[@]}"; then
      echo "$(ts) [OK] Scripts terminaron con SIGTERM"
    else
      echo "$(ts) [WARN] Aún quedan scripts → SIGKILL"
      sig_pids KILL "${FILTERED_PIDS[@]}"
      sleep 0.5
    fi
  fi
else
  echo "$(ts) [INFO] No hay PIDs de scripts para detener."
fi

# 4) Limpieza de listado (scripts)
: > "$PIDS_FILE" 2>/dev/null || true

# 5) Cierra sesiones Appium principales (libera 4723/4730/4786)
for p in "${APPIUM_PORTS[@]}"; do close_sessions "$p"; done

# 6) (NUEVO) End Log en G-Net (Whats A) con Appium temporal 4790, DESPUÉS de liberar el cel de Whats
PYBIN="/home/jetson/Desktop/Split Llamadas/.venv/bin/python"
SCRIPT_GNET_WHATS_STOP="$SCRIPT_DIR/G-net/gnet_stop_on_whatsA.py"
PORT_GNET_WHATS_TMP=4790

port_up() {
  if command -v ss >/dev/null 2>&1; then
    ss -H -ltn "sport = :${1}" 2>/dev/null | grep -q .
  else
    lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
  fi
}
wait_appium(){
  local port="$1"; local url="http://127.0.0.1:${port}/status"
  for _ in {1..30}; do curl -sf "$url" >/dev/null 2>&1 && return 0; sleep 1; done
  return 1
}
wait_port_sessions_drained(){
  local port="$1"
  for _ in {1..20}; do
    [[ -z "$(list_sessions "$port")" ]] && return 0
    sleep 1
  done
  return 1
}

if [[ -f "$SCRIPT_GNET_WHATS_STOP" ]]; then
  echo "$(ts) [INFO] Esperando a que 4723 quede sin sesiones…"
  wait_port_sessions_drained 4723 || echo "$(ts) [WARN] 4723 aún tenía sesiones; continúo igual."

  echo "$(ts) [INFO] End Log en Whats A: preparando Appium ${PORT_GNET_WHATS_TMP}…"
  TMP_APPIUM_PID=""
  if ! port_up "$PORT_GNET_WHATS_TMP"; then
    if command -v appium >/dev/null 2>&1; then APPIUM_CMD=(appium)
    elif command -v npx >/dev/null 2>&1; then APPIUM_CMD=(npx appium)
    else echo "$(ts) [WARN] No hay 'appium' ni 'npx' en PATH; salto End Log de Whats."; goto_skip_endlog=1; fi
    if [[ -z "${goto_skip_endlog:-}" ]]; then
      nohup "${APPIUM_CMD[@]}" --relaxed-security -p "$PORT_GNET_WHATS_TMP" >"$HOME/appium-${PORT_GNET_WHATS_TMP}.log" 2>&1 &
      TMP_APPIUM_PID=$!
      echo "$(ts) [INFO] Appium ${PORT_GNET_WHATS_TMP} lanzado (pid=$TMP_APPIUM_PID)."
      wait_appium "$PORT_GNET_WHATS_TMP" || echo "$(ts) [WARN] Appium ${PORT_GNET_WHATS_TMP} no respondió /status."
    fi
  else
    echo "$(ts) [INFO] Appium ${PORT_GNET_WHATS_TMP} ya estaba arriba; lo reutilizo."
  fi

  if [[ -z "${goto_skip_endlog:-}" ]]; then
    echo "$(ts) [INFO] Ejecutando End Log (Whats A)…"
    "$PYBIN" "$SCRIPT_GNET_WHATS_STOP" || echo "$(ts) [WARN] gnet_stop_on_whatsA.py devolvió error (continúo)."
  fi

  # Cerrar Appium temporal solo si lo lanzamos aquí
  if [[ -n "${TMP_APPIUM_PID:-}" ]] && kill -0 "$TMP_APPIUM_PID" 2>/dev/null; then
    echo "$(ts) [INFO] Cerrando Appium temporal ${PORT_GNET_WHATS_TMP} (pid=${TMP_APPIUM_PID})…"
    kill "$TMP_APPIUM_PID" 2>/dev/null || true
    sleep 0.4
    kill -0 "$TMP_APPIUM_PID" 2>/dev/null && kill -9 "$TMP_APPIUM_PID" 2>/dev/null || true
  fi
fi

# 7) Stop del GPS opcional
if command -v adb >/dev/null 2>&1; then
  if adb devices 2>/dev/null | awk 'NR>1 && $2=="device"{print $1}' | grep -q "^${DEVICE_WHATS}$"; then
    echo "$(ts) [INFO] Deteniendo servicio 'viva.vast/.GpsService' en ${DEVICE_WHATS}…"
    adb -s "${DEVICE_WHATS}" shell am stopservice -n viva.vast/.GpsService || true
  else
    echo "$(ts) [INFO] ${DEVICE_WHATS} no está en 'device'; omito stopservice."
  fi
fi

# 8) Limpia flags locales de Whats; NO borres STOP_ALL (lo borra autostart al salir)
rm -f "$STOP_FLAG" 2>/dev/null || true

echo "$(ts) [OK] stop_finale.sh completado."
