#!/usr/bin/env bash
set -euo pipefail

# ================== BASE ==================
ROOT="/home/pi/Desktop/Finale_Alva"
LOGS="$ROOT/logs"
PIDS="$ROOT/pids"
STOP_FLAG="$PIDS/STOP.flag"
mkdir -p "$LOGS" "$PIDS"

# ANDROID / PATH
export ANDROID_HOME=/home/pi/Android
export ANDROID_SDK_ROOT=/home/pi/Android
# Prioriza appium del usuario
export PATH="$HOME/.npm-global/bin:$ANDROID_HOME/platform-tools:/usr/bin:/usr/local/bin:$PATH"
export DISPLAY=:0

# Aislar Appium y cache npm en el proyecto
export APPIUM_HOME="$ROOT/.appium-home"
export npm_config_cache="$ROOT/.npm-cache"
mkdir -p "$APPIUM_HOME" "$npm_config_cache"

# Python (usa venv si existe)
if [[ -x "/home/pi/Desktop/Testdrive/venv/bin/python" ]]; then
  PY="/home/pi/Desktop/Testdrive/venv/bin/python"
  # shellcheck disable=SC1091
  source /home/pi/Desktop/Testdrive/venv/bin/activate
else
  PY="${PY:-$(command -v python3 || true)}"
fi
[[ -z "${PY:-}" ]] && { echo "[ERROR] python3 no encontrado"; exit 1; }

# Appium binario (appium o npx appium)
APPIUM_BIN="${APPIUM_BIN:-$(command -v appium || true)}"
if [[ -z "$APPIUM_BIN" ]] && command -v npx >/dev/null 2>&1; then
  APPIUM_BIN="npx appium"
fi

ts() { date +"[%F %T]"; }

# ================== HELPERS RED / PUERTOS ==================
port_up() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -H -ltn "sport = :${port}" | grep -q . || return 1
  else
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1 || return 1
  fi
  return 0
}
appium_ready() { curl -sf --max-time 2 "http://127.0.0.1:$1/status" 2>/dev/null | grep -q '"ready"' || return 1; }
wait_port() { local port="$1" tries="${2:-60}"; for ((i=0;i<tries;i++)); do port_up "$port" && return 0; sleep 0.2; done; return 1; }
wait_appium_ready() { local port="$1" tries="${2:-40}"; for ((i=0;i<tries;i++)); do appium_ready "$port" && return 0; sleep 0.5; done; return 1; }

kill_with_pidfile() {
  local pidfile="$1"
  [[ -f "$pidfile" ]] || { rm -f "$pidfile" 2>/dev/null || true; return 0; }
  local pid; pid="$(cat "$pidfile" 2>/dev/null || true)"
  if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    sleep 0.5
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$pidfile" 2>/dev/null || true
  return 0
}

ensure_device() {
  local udid="$1" tries=10
  command -v adb >/dev/null 2>&1 || { echo "[ERROR] adb no está en PATH"; return 1; }
  for ((i=0;i<tries;i++)); do
    if adb -s "$udid" get-state 2>/dev/null | grep -q "^device$"; then
      return 0
    fi
    sleep 1
  done
  echo "[WARN] $udid no está en 'device'"; adb devices || true
  return 1
}

# ================== APPIUM PUERTOS ==================
declare -A APPIUM_PORT
APPIUM_PORT[serie]=4723    # Nativo
APPIUM_PORT[gtrack]=4783   # Alva (browser)
APPIUM_PORT[cell]=4793     # Calls

pre_kill_appium_ports() {
  echo "$(ts) [INFO] Cerrando Appium en puertos 4723,4783,4793 si existen..."
  lsof -ti tcp:4723,4783,4793 2>/dev/null | xargs -r kill -9 || true
  echo "$(ts) [INFO] Liberando systemPorts (host): 8000,8001,8200,8201,8210,8220,8230,8240 ..."
  lsof -ti tcp:8000,8001,8200,8201,8210,8220,8230,8240 2>/dev/null | xargs -r kill -9 || true
}

start_appium() {
  [[ -n "$APPIUM_BIN" ]] || { echo "$(ts) [WARN] 'appium' no encontrado (ni via npx). Omite start_appium"; return 0; }

  : > "$LOGS/appium-serie-${APPIUM_PORT[serie]}.log"
  : > "$LOGS/appium-gtrack-${APPIUM_PORT[gtrack]}.log"
  : > "$LOGS/appium-cell-${APPIUM_PORT[cell]}.log"

  for role in serie gtrack cell; do
    local port="${APPIUM_PORT[$role]}"
    local log="$LOGS/appium-$role-$port.log"

    if port_up "$port"; then
      echo "$(ts) [INFO] appium ($role) ya en $port"
      appium_ready "$port" || { echo "$(ts) [INFO] esperando ready en $port..."; wait_appium_ready "$port" || true; }
      continue
    fi

    echo "$(ts) [INFO] lanzando appium ($role) en puerto $port"
    local extra=( --relaxed-security --session-override )
    [[ "$port" == "4783" ]] && extra+=( --allow-insecure=chromedriver_autodownload )

    local cmd="$APPIUM_BIN -p $port ${extra[*]}"
    nohup bash -lc "$cmd" > "$log" 2>&1 &
    echo $! > "$PIDS/appium-$role-$port.pid"

    wait_port "$port" || echo "[WARN] puerto $port no abrió aún"
    wait_appium_ready "$port" || echo "[WARN] appium $port no confirmó ready aún"
    sleep 0.2
  done
  return 0
}

start_appium_force() { pre_kill_appium_ports; start_appium; }

stop_appium() {
  for role in serie gtrack cell; do
    local port="${APPIUM_PORT[$role]}"
    kill_with_pidfile "$PIDS/appium-$role-$port.pid"
  done
  lsof -ti tcp:4723,4783,4793 2>/dev/null | xargs -r kill -9 || true
  return 0
}

ensure_appium_up() {
  local need=0
  for role in serie gtrack cell; do
    local port="${APPIUM_PORT[$role]}"
    if ! port_up "$port"; then need=1; break; fi
  done
  if [[ $need -eq 1 ]]; then
    start_appium || true
  fi
  return 0
}

# ----- Cierre de sesiones colgadas (sin bajar servidor) -----
list_sessions() {
  local port="$1"
  curl -sf --max-time 2 "http://127.0.0.1:$port/sessions" 2>/dev/null \
    | grep -oE '"id"\s*:\s*"[^"]+"' 2>/dev/null \
    | sed -E 's/.*"id"\s*:\s*"([^"]+)".*/\1/' 2>/dev/null || true
}
close_sessions() {
  local port="$1"
  echo "$(ts) [INFO] Cerrando sesiones en $port..."
  local sid
  for sid in $(list_sessions "$port"); do
    curl -s -X DELETE "http://127.0.0.1:$port/session/$sid" >/dev/null 2>&1 || true
    sleep 0.2
  done
  return 0
}

# ================== SCRIPTS PY (UDID) ==================
declare -A PATHS CWDS NAMES LOGF UDID
NAMES[serie]="Serie"; PATHS[serie]="$ROOT/Nativo/Serie.py";    CWDS[serie]="$ROOT/Nativo";    LOGF[serie]="$LOGS/Serie.log";  UDID[serie]="R58MA32XQQW"
NAMES[gtrack]="Alva"; PATHS[gtrack]="$ROOT/Alva_Net/alva.py";  CWDS[gtrack]="$ROOT/Alva_Net"; LOGF[gtrack]="$LOGS/Alva.log";  UDID[gtrack]="R58M795NHZF"
NAMES[cell]="cell";   PATHS[cell]="$ROOT/Calls/Calls.py";      CWDS[cell]="$ROOT/Calls";      LOGF[cell]="$LOGS/Calls.log";   UDID[cell]="RF8MB0G4KTJ"

wait_for_devices() {
  echo "$(ts) [INFO] Esperando 3 dispositivos ADB en estado 'device'..."
  for _ in {1..60}; do
    local total
    total=$(adb devices | grep -w "device" | grep -v "List" | wc -l | tr -d ' ' || echo 0)
    [[ "${total:-0}" -eq 3 ]] && { echo "$(ts) [INFO] 3/3 detectados. Continuando..."; return 0; }
    sleep 1.5
  done
  echo "$(ts) [WARN] No se detectaron 3 dispositivos tras el tiempo esperado."
  return 1
}

# *** IMPORTANTE: limpia uia2 y ENCIENDE el GPS service (viva.vast) en cada device ***
pre_clean_uia2_host_devices() {
  echo "$(ts) [INFO] Limpiando uiautomator2 en devices + systemPorts huérfanos en host..."
  for ud in "${UDID[serie]}" "${UDID[gtrack]}" "${UDID[cell]}"; do
    [[ -n "$ud" ]] || continue
    adb -s "$ud" shell am force-stop io.appium.uiautomator2.server io.appium.uiautomator2.server.test >/dev/null 2>&1 || true
    # Enciende el servicio de GPS (si está instalado); es idempotente
    adb -s "$ud" shell am start-foreground-service -n viva.vast/.GpsService >/dev/null 2>&1 || true
  done
  # Limpia systemPorts por si quedaron zombies
  lsof -ti tcp:8000,8001,8200,8201,8210,8220,8230,8240 2>/dev/null | xargs -r kill -9 || true
}

# ===== Helpers de PID/PGID =====
clean_pid_artifacts() { rm -f "$PIDS/"*.pid "$PIDS/"*.pgid "$PIDS/"*.exit 2>/dev/null || true; }
already_running() { local key="$1"; local pidfile="$PIDS/$key.pid"; [[ -f "$pidfile" ]] && pid="$(cat "$pidfile" 2>/dev/null || true)"; [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; }

start_scripts() {
  echo "$(ts) [INFO] Lanzando scripts…"
  : > "$LOGS/Serie.log"; : > "$LOGS/Alva.log"; : > "$LOGS/Calls.log"

  wait_for_devices || true
  pre_clean_uia2_host_devices

  for key in serie gtrack cell; do
    local path="${PATHS[$key]}" cwd="${CWDS[$key]}" name="${NAMES[$key]}" log="${LOGF[$key]}" dev="${UDID[$key]}"

    if [[ ! -f "$path" ]]; then echo "[WARN] No existe: $path"; continue; fi
    if ! ensure_device "$dev"; then echo "[WARN] Omito $name; $dev no disponible"; continue; fi
    if already_running "$key"; then echo "[INFO] $name ya corre, omito launch"; continue; fi

    echo "$(ts) [INFO] lanzando $name (UDID=$dev) -> $path"

    local bash_cmd
    bash_cmd="cd '$cwd' && export ANDROID_SERIAL='$dev' ADB_SERIAL='$dev' PYTHONUNBUFFERED=1; stdbuf -oL -eL -- '$PY' '$path' 2>&1 | awk '{ print strftime(\"[%F %T]\"), \$0; fflush(); }' >> '$log'"

    setsid bash -lc "$bash_cmd" &
    local child=$!
    echo "$child" > "$PIDS/$key.pid"
    local pgid
    pgid="$(ps -o pgid= -p "$child" | tr -d ' ')"
    echo "$pgid" > "$PIDS/$key.pgid"
    ( wait "$child"; echo $? > "$PIDS/$key.exit" ) >/dev/null 2>&1 &
    sleep 0.1
  done
  echo "$(ts) [INFO] Scripts lanzados (si estaban disponibles)."
}

stop_scripts() {
  set +e
  echo "$(ts) [INFO] STOP scripts: pedir apagado elegante y cerrar sesiones colgadas"

  for key in serie gtrack cell; do
    local name="${NAMES[$key]}" pidfile="$PIDS/$key.pid"
    if [[ -f "$pidfile" ]]; then
      local pid; pid="$(cat "$pidfile" 2>/dev/null || true)"
      if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
        local pgid
        if [[ -f "$PIDS/$key.pgid" ]]; then
          pgid="$(cat "$PIDS/$key.pgid" 2>/dev/null || true)"
        else
          pgid="$(ps -o pgid= -p "$pid" | tr -d ' ')"
        fi
        echo "$(ts) [INFO] Enviando SIGTERM a $name (pid=$pid, pgid=$pgid). Esperando apagado elegante..."
        kill -TERM "-$pgid" 2>/dev/null || kill "$pid" 2>/dev/null || true

        for _ in {1..30}; do
          kill -0 "$pid" 2>/dev/null || { echo "$(ts) [OK] $name salió limpiamente"; break; }
          sleep 1
        done

        if kill -0 "$pid" 2>/dev/null; then
          echo "$(ts) [WARN] $name no salió a tiempo; escalando a KILL de grupo..."
          kill -KILL "-$pgid" 2>/dev/null || true
          sleep 0.5
        fi
      fi
      rm -f "$pidfile" "$PIDS/$key.pgid" "$PIDS/$key.exit" 2>/dev/null || true
    fi
  done

  # Cerrar sesiones Appium (previo a detener servicios)
  for role in serie gtrack cell; do
    local port="${APPIUM_PORT[$role]}"
    close_sessions "$port"
  done

  echo "$(ts) [INFO] Deteniendo uiautomator2 en devices..."
  for ud in "${UDID[serie]}" "${UDID[gtrack]}" "${UDID[cell]}"; do
    [[ -n "$ud" ]] || continue
    adb -s "$ud" shell am force-stop io.appium.uiautomator2.server io.appium.uiautomator2.server.test >/dev/null 2>&1 || true
  done

  # Apaga SIEMPRE el servicio de GPS
  echo "$(ts) [INFO] Apagando servicio GPS (viva.vast) en devices..."
  for ud in "${UDID[serie]}" "${UDID[gtrack]}" "${UDID[cell]}"; do
    [[ -n "$ud" ]] || continue
    adb -s "$ud" shell am stopservice -n viva.vast/.GpsService >/dev/null 2>&1 || true
    adb -s "$ud" shell am force-stop viva.vast >/dev/null 2>&1 || true
  done

  # Cierre de logs/app G-NetTrack + apps extra (script en raíz)
  echo "$(ts) [INFO] Ejecutando cierre de logs G-NetTrack en los 3 devices..."
  PYTHONPATH="$ROOT:$ROOT/Nativo:$ROOT/Calls:$ROOT/Alva_Net:${PYTHONPATH:-}" \
    "$PY" "$ROOT/gnettrack_stop_all.py" || echo "[WARN] gnettrack_stop_all devolvió error"

  # **LIMPIEZA FINAL**: barrer cualquier sesión residual
  for role in serie gtrack cell; do
    local port="${APPIUM_PORT[$role]}"
    close_sessions "$port" || true
  done

  rm -f "$STOP_FLAG" 2>/dev/null || true
  set -e
}

sessions_count() {
  local port=""
  python3 - "" <<'PY'
import sys, json, urllib.request
port=int(sys.argv[1])
try:
    data=json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/sessions"))
    print(len(data.get("value", [])))
except Exception:
    print(0)
PY
}
sessions_status() {
  echo "== APPIUM SESSIONS =="
  for role in serie gtrack cell; do
    local port=""
    if port_up ""; then
      local cnt; cnt="1000 4 20 24 27 29 44 46 60 100 102 105 110 115 993 994 995 1000sessions_count "")"
      echo "   () ->  sesiones"
    else
      echo "   () -> DOWN"
    fi
  done
}
show_logs() {
  echo "== LOGS (últimas 80 líneas) =="
  for key in serie gtrack cell; do
    local log="${LOGF[$key]}"
    echo "---- ${NAMES[$key]} -> $log ----"
    [[ -f "$log" ]] && tail -n 80 "$log" || echo "(no existe log aún)"
    echo
  done
}
status_all() {
  echo "== APPIUM =="
  for role in serie gtrack cell; do
    local port="${APPIUM_PORT[$role]}"
    if port_up "$port"; then
      echo "  appium:$role:$port -> UP"
    else
      echo "  appium:$role:$port -> DOWN"
    fi
  done
  echo "== SCRIPTS =="
  for key in serie gtrack cell; do
    local name="${NAMES[$key]}" pidfile="$PIDS/$key.pid"
    if [[ -f "$pidfile" ]]; then
      local pid; pid="$(cat "$pidfile" 2>/dev/null || true)"
      if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
        echo "  $name -> PID $pid"
        continue
      fi
    fi
    echo "  $name -> DOWN"
  done
}

# ===== Helpers para START =====
wait_appium_all_ready() {
  ensure_appium_up || true
  for role in serie gtrack cell; do
    local port="${APPIUM_PORT[$role]}"
    wait_appium_ready "$port" || echo "$(ts) [WARN] appium $role:$port aún no reporta ready"
  done
  return 0
}
clean_before_start() {
  for role in serie gtrack cell; do
    local port="${APPIUM_PORT[$role]}"
    close_sessions "$port" || true
  done
  pre_clean_uia2_host_devices
  rm -f "$STOP_FLAG" 2>/dev/null || true
  return 0
}

# ================== CLI ==================
case "${1:-start}" in
  start)
    wait_for_devices || true
    wait_appium_all_ready
    clean_before_start
    start_scripts
    status_all; sessions_status
    ;;
  stop)
    stop_scripts
    status_all; sessions_status
    ;;
  reset)
    stop_scripts
    stop_appium
    sleep 1
    start_appium_force
    sleep 1
    start_scripts
    status_all; sessions_status
    ;;
  logs)
    show_logs
    ;;
  status)
    status_all; sessions_status
    ;;
  scripts-start)
    wait_appium_all_ready
    clean_before_start
    start_scripts
    status_all
    ;;
  scripts-stop)
    stop_scripts
    status_all
    ;;
  *)
    echo "Uso: $0 {start|stop|reset|status|logs|scripts-start|scripts-stop}"
    exit 1
    ;;
esac

# --- Guardia anti-respawn de sesiones Appium (mantiene 0 por ~15s) ---
guard_zero_sessions() {
  local ports=(4723 4783 4793)
  for port in "${ports[@]}"; do
    for i in {1..15}; do
      local c; c="$(sessions_count "$port")"
      if [[ "${c:-0}" -eq 0 ]]; then
        break
      fi
      echo "$(ts) [WARN] $port aún tiene $c sesiones; forzando DELETE…"
      close_sessions "$port"
      sleep 1
    done
    local final; final="$(sessions_count "$port")"
    echo "$(ts) [INFO] Guardia en $port => ${final} sesiones"
  done
}
