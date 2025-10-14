#!/usr/bin/env bash
set -euo pipefail

# ================== BASE ==================
ROOT="/home/pi/Desktop/Finale_Alva"
LOGS="$ROOT/logs"
PIDS="$ROOT/pids"
mkdir -p "$LOGS" "$PIDS"

# ANDROID / PATH
export ANDROID_HOME=/home/pi/Android
export ANDROID_SDK_ROOT=/home/pi/Android
export PATH="$PATH:$ANDROID_HOME/platform-tools:/usr/bin:/usr/local/bin:/home/pi/.npm-global/bin"
export DISPLAY=:0

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
    ss -H -ltn "sport = :${port}" | grep -q .
  else
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
  fi
}
appium_ready() { curl -s --max-time 2 "http://127.0.0.1:$1/status" | grep -q '"ready"'; }

wait_port() {
  local port="$1" tries="${2:-60}"
  for ((i=0;i<tries;i++)); do port_up "$port" && return 0; sleep 0.2; done
  return 1
}
wait_appium_ready() {
  local port="$1" tries="${2:-40}"
  for ((i=0;i<tries;i++)); do appium_ready "$port" && return 0; sleep 0.5; done
  return 1
}

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
}

ensure_device() {
  local udid="$1"
  command -v adb >/dev/null 2>&1 || { echo "[ERROR] adb no está en PATH"; return 1; }
  adb -s "$udid" get-state 2>/dev/null | grep -q "^device$" || { echo "[WARN] $udid no está en 'device'"; adb devices; return 1; }
}

# ================== APPIUM PUERTOS ==================
declare -A APPIUM_PORT
APPIUM_PORT[serie]=4723    # Nativo
APPIUM_PORT[gtrack]=4783   # Alva (browser)
APPIUM_PORT[cell]=4793     # Calls

pre_kill_appium_ports() {
  echo "$(ts) [INFO] Cerrando Appium en puertos 4723,4783,4793 si existen..."
  lsof -ti tcp:4723,4783,4793 2>/dev/null | xargs -r kill -9 || true
  echo "$(ts) [INFO] Liberando systemPorts (host): 8000,8001,8210,8220 ..."
  lsof -ti tcp:8000,8001,8210,8220 2>/dev/null | xargs -r kill -9 || true
}

start_appium() {
  [[ -n "$APPIUM_BIN" ]] || { echo "$(ts) [WARN] 'appium' no encontrado (ni via npx). Omite start_appium"; return; }

  : > "$LOGS/appium-serie-${APPIUM_PORT[serie]}.log"
  : > "$LOGS/appium-gtrack-${APPIUM_PORT[gtrack]}.log"
  : > "$LOGS/appium-cell-${APPIUM_PORT[cell]}.log"

  for role in serie gtrack cell; do
    port="${APPIUM_PORT[$role]}"
    log="$LOGS/appium-$role-$port.log"

    if port_up "$port"; then
      echo "$(ts) [INFO] appium ($role) ya en $port"
      appium_ready "$port" || { echo "$(ts) [INFO] esperando ready en $port..."; wait_appium_ready "$port" || true; }
      continue
    fi

    echo "$(ts) [INFO] lanzando appium ($role) en puerto $port"
    extra=( --relaxed-security )
    [[ "$port" == "4783" ]] && extra+=( --allow-insecure=chromedriver_autodownload )

    cmd="$APPIUM_BIN -p $port ${extra[*]}"
    nohup bash -lc "$cmd" > "$log" 2>&1 &
    echo $! > "$PIDS/appium-$role-$port.pid"

    wait_port "$port" || echo "[WARN] puerto $port no abrió aún"
    wait_appium_ready "$port" || echo "[WARN] appium $port no confirmó ready aún"
    sleep 0.2
  done
}

# Arranque forzado (para reset/primer boot): mata puertos y levanta de cero
start_appium_force() { pre_kill_appium_ports; start_appium; }

stop_appium() {
  for role in serie gtrack cell; do
    port="${APPIUM_PORT[$role]}"
    kill_with_pidfile "$PIDS/appium-$role-$port.pid"
  done
  lsof -ti tcp:4723,4783,4793 2>/dev/null | xargs -r kill -9 || true
}

# Asegura Appium arriba si falta en alguno de los puertos (no mata nada)
ensure_appium_up() {
  local need=0
  for role in serie gtrack cell; do
    port="${APPIUM_PORT[$role]}"
    if ! port_up "$port"; then need=1; break; fi
  done
  [[ $need -eq 1 ]] && start_appium
}

# ----- Cierre de sesiones colgadas (sin bajar servidor) -----
list_sessions() {
  local port="$1"
  curl -s --max-time 2 "http://127.0.0.1:$port/sessions" \
    | grep -oE '"id"\s*:\s*"[^"]+"' \
    | sed -E 's/.*"id"\s*:\s*"([^"]+)".*/\1/'
}
close_sessions() {
  local port="$1"
  echo "$(ts) [INFO] Cerrando sesiones en $port..."
  local sid
  for sid in $(list_sessions "$port"); do
    curl -s -X DELETE "http://127.0.0.1:$port/session/$sid" >/dev/null 2>&1 || true
    sleep 0.2
  done
}

# ================== SCRIPTS PY (UDID) ==================
declare -A PATHS CWDS NAMES LOGF UDID
NAMES[serie]="Serie"; PATHS[serie]="$ROOT/Nativo/Serie.py";    CWDS[serie]="$ROOT/Nativo";    LOGF[serie]="$LOGS/Serie.log";  UDID[serie]="R58MA32XQQW"
NAMES[gtrack]="Alva"; PATHS[gtrack]="$ROOT/Alva_Net/alva.py";  CWDS[gtrack]="$ROOT/Alva_Net"; LOGF[gtrack]="$LOGS/Alva.log";  UDID[gtrack]="R58M795NHZF"
NAMES[cell]="cell";   PATHS[cell]="$ROOT/Calls/Calls.py";      CWDS[cell]="$ROOT/Calls";      LOGF[cell]="$LOGS/Calls.log";   UDID[cell]="RF8MB0G4KTJ"

wait_for_devices() {
  echo "$(ts) [INFO] Esperando 3 dispositivos ADB en estado 'device'..."
  for i in {1..60}; do
    total=$(adb devices | grep -w "device" | grep -v "List" | wc -l)
    [[ "$total" -eq 3 ]] && { echo "$(ts) [INFO] 3/3 detectados. Continuando..."; return 0; }
    sleep 1.5
  done
  echo "$(ts) [WARN] No se detectaron 3 dispositivos tras el tiempo esperado."
  return 1
}

# Limpia uiautomator2 y systemPorts de host (sin bajar appium)
pre_clean_uia2_host_devices() {
  echo "$(ts) [INFO] Limpiando systemPorts 8000,8001,8210,8220 en host y uiautomator2 en devices..."
  lsof -ti tcp:8000,8001,8210,8220 2>/dev/null | xargs -r kill -9 || true
  for ud in "${UDID[serie]}" "${UDID[gtrack]}" "${UDID[cell]}"; do
    [[ -n "$ud" ]] || continue
    adb -s "$ud" shell am force-stop io.appium.uiautomator2.server io.appium.uiautomator2.server.test >/dev/null 2>&1 || true
  done
  # GPS idempotente (no hace daño si ya corre)
  adb -s "${UDID[cell]}"   shell am start-foreground-service -n viva.vast/.GpsService >/dev/null 2>&1 || true
  adb -s "${UDID[serie]}"  shell am start-foreground-service -n viva.vast/.GpsService >/dev/null 2>&1 || true
  adb -s "${UDID[gtrack]}" shell am start-foreground-service -n viva.vast/.GpsService >/dev/null 2>&1 || true
}

start_scripts() {
  : > "$LOGS/Serie.log"; : > "$LOGS/Alva.log"; : > "$LOGS/Calls.log"
  wait_for_devices || true
  pre_clean_uia2_host_devices
  for key in serie gtrack cell; do
    local path="${PATHS[$key]}" cwd="${CWDS[$key]}" name="${NAMES[$key]}" log="${LOGF[$key]}" dev="${UDID[$key]}"
    if [[ ! -f "$path" ]]; then echo "[WARN] No existe: $path"; continue; fi
    if ! ensure_device "$dev"; then echo "[WARN] Omito $name; $dev no disponible"; continue; fi
    echo "$(ts) [INFO] lanzando $name (UDID=$dev) -> $path"

    (
      cd "$cwd" || exit 1
      export ANDROID_SERIAL="$dev" ADB_SERIAL="$dev" PYTHONUNBUFFERED=1
      set -o pipefail
      (
        "$PY" "$path"
      ) 2>&1 | awk '{ print strftime("[%F %T]"), $0; fflush(); }' | tee -a "$log"
      ec=${PIPESTATUS[0]}
      echo "$ec" > "$PIDS/$key.exit"
      exit "$ec"
    ) & echo $! > "$PIDS/$key.pid"

    sleep 0.2
  done
}

# Apagado elegante: SIGTERM -> espera -> kill de grupo si persiste
stop_scripts() {
  echo "$(ts) [INFO] STOP scripts: pedir apagado elegante y cerrar sesiones colgadas"
  for key in serie gtrack cell; do
    local name="${NAMES[$key]}" pidfile="$PIDS/$key.pid"
    if [[ -f "$pidfile" ]]; then
      local pid; pid="$(cat "$pidfile" 2>/dev/null || true)"
      if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
        echo "$(ts) [INFO] Enviando SIGTERM a $name (pid=$pid). Esperando apagado elegante..."
        kill "$pid" 2>/dev/null || true

        # Espera cooperativa (scripts ya manejan SIGTERM con 'detener' / cierre de driver)
        for _ in {1..30}; do
          kill -0 "$pid" 2>/dev/null || { echo "$(ts) [OK] $name salió limpiamente"; break; }
          sleep 1
        done

        # Si sigue vivo, kill de grupo
        if kill -0 "$pid" 2>/dev/null; then
          echo "$(ts) [WARN] $name no salió a tiempo; escalando a KILL de grupo..."
          kill -9 "-$pid" 2>/dev/null || true
          sleep 0.5
        fi
      fi
      rm -f "$pidfile" 2>/dev/null || true
    fi
  done

  # Cerrar sesiones colgadas en todos los puertos (sin bajar Appium)
  for role in serie gtrack cell; do
    port="${APPIUM_PORT[$role]}"
    close_sessions "$port"
  done
}

sessions_count() { curl -s --max-time 2 "http://127.0.0.1:$1/sessions" | grep -o '"id"' | wc -l | tr -d ' '; }
sessions_status() {
  echo "== APPIUM SESSIONS =="
  for role in serie gtrack cell; do
    port="${APPIUM_PORT[$role]}"
    if port_up "$port"; then
      echo "  $role ($port) -> $(sessions_count "$port") sesiones"
    else
      echo "  $role ($port) -> DOWN"
    fi
  done
}
show_logs() {
  echo "== LOGS (últimas 80 líneas) =="
  for key in serie gtrack cell; do
    log="${LOGF[$key]}"
    echo "---- ${NAMES[$key]} -> $log ----"
    [[ -f "$log" ]] && tail -n 80 "$log" || echo "(no existe log aún)"
    echo
  done
}

status_all() {
  echo "== APPIUM =="
  for role in serie gtrack cell; do
    port="${APPIUM_PORT[$role]}"
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
      pid="$(cat "$pidfile" 2>/dev/null || true)"
      if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
        echo "  $name -> PID $pid"
        continue
      fi
    fi
    echo "  $name -> DOWN"
  done
}

# ================== CLI ==================
case "${1:-start}" in
  start)
    ensure_appium_up        # No mata Appium; levanta sólo el que falte
    start_scripts
    status_all; sessions_status
    ;;
  stop)
    stop_scripts            # Deja Appium UP; cierra sesiones colgadas
    status_all; sessions_status
    ;;
  reset)
    stop_scripts
    stop_appium
    sleep 1
    start_appium_force      # Mata puertos + Appium limpio
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
    ensure_appium_up
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

