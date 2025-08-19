#!/bin/bash
set -u -o pipefail

# --- VARIABLES ANDROID ---
export ANDROID_HOME=/home/pi/Android
export ANDROID_SDK_ROOT=/home/pi/Android
export PATH=$PATH:$ANDROID_HOME/platform-tools:/usr/bin:/usr/local/bin:/home/pi/.npm-global/bin
export DISPLAY=:0
export APPIUM_HOME=/home/pi/.appium_a2   # <<<<<< AÑADIDO

# --- LIMPIAR LOGS ANTERIORES ---
: > /home/pi/appium_4723.log
: > /home/pi/appium_4725.log
: > /home/pi/appium_4727.log
: > /home/pi/test_output.log
: > /home/pi/start_test_autostart.log
: > /home/pi/instagram.log
: > /home/pi/whatsapp.log
: > /home/pi/facebook.log

# --- DIAGNÓSTICO DE ARRANQUE ---
echo "Script ejecutado a: $(date)" >> /home/pi/start_test_autostart.log

# --- ADB PREP ---
echo "[ADB] start-server" >> /home/pi/test_output.log
adb start-server >> /home/pi/test_output.log 2>&1 || true

# --- LIBERAR PUERTOS USADOS POR ADB/APPIUM ---
echo "Cerrando procesos en puertos 4723, 4725 y 4727..." >> /home/pi/test_output.log
for port in 4723 4725 4727; do
  pid=$(sudo lsof -ti tcp:$port || true)
  if [ -n "${pid:-}" ]; then
    echo "Matando proceso en puerto $port (PID $pid)..." >> /home/pi/test_output.log
    sudo kill -9 $pid || true
  fi
done
sleep 1

# --- LIBERAR systemPorts de UiAutomator2 (host) ---
echo "Liberando systemPorts 8200-8202..." >> /home/pi/test_output.log
sudo lsof -ti tcp:8200,8201,8202 | xargs -r sudo kill -9

# --- ESPERAR DISPOSITIVOS ADB ---
echo "Esperando que se conecten 3 dispositivos ADB..." >> /home/pi/test_output.log
for i in {1..60}; do
  total=$(adb devices | grep -w "device" | grep -v "List" | wc -l)
  if [ "$total" -eq 3 ]; then
    echo "Dispositivos detectados correctamente." >> /home/pi/test_output.log
    break
  else
    echo "Detectados: $total/3. Reintentando..." >> /home/pi/test_output.log
    sleep 2
  fi
done

# --- LIMPIAR UiAutomator2 en los dispositivos ---
for ud in RF8MB0G4KTJ R58MA32XQQW R58M795NHZF; do
  adb -s "$ud" shell am force-stop io.appium.uiautomator2.server io.appium.uiautomator2.server.test || true
done

# --- INICIAR GPS (no hace daño si ya corre) ---
adb -s RF8MB0G4KTJ shell am start-foreground-service -n viva.vast/.GpsService || true
adb -s R58MA32XQQW shell am start-foreground-service -n viva.vast/.GpsService || true
adb -s R58M795NHZF shell am start-foreground-service -n viva.vast/.GpsService || true

# --- RESOLVER BINARIO APPIUM ---
APPIUM_BIN="$(command -v appium || true)"
if [ -z "$APPIUM_BIN" ]; then
  if command -v npx >/dev/null 2>&1; then
    APPIUM_BIN="npx appium"
  else
    echo "[ERROR] No se encontró 'appium' ni 'npx'. Agrega Appium al PATH o instala con: npm i -g appium" | tee -a /home/pi/test_output.log
    exit 1
  fi
fi
echo "[OK] Usando Appium: $APPIUM_BIN" >> /home/pi/test_output.log

# --- FUNCIÓN: arrancar y validar un servidor Appium ---
start_appium_port() {
  local PORT="$1"
  local LOGFILE="/home/pi/appium_${PORT}.log"
  echo "Iniciando Appium en puerto ${PORT}..." >> /home/pi/test_output.log

  bash -lc "$APPIUM_BIN --relaxed-security -p ${PORT} >> ${LOGFILE} 2>&1 & echo \$!" > /tmp/appium_${PORT}.pid
  local APPIUM_PID
  APPIUM_PID=$(cat /tmp/appium_${PORT}.pid 2>/dev/null || true)

  for i in {1..20}; do
    if curl -s "http://127.0.0.1:${PORT}/status" | grep -q '"ready":'; then
      echo "[OK] Appium ${PORT} listo (PID ${APPIUM_PID})." >> /home/pi/test_output.log
      return 0
    fi
    sleep 0.5
  done

  echo "[ERROR] Appium no respondió en ${PORT}. Revisa ${LOGFILE}" | tee -a /home/pi/test_output.log
  return 1
}

# --- INICIAR SERVIDORES APPIUM ---
start_appium_port 4723 || true
start_appium_port 4725 || true
start_appium_port 4727 || true
echo "Servidores Appium iniciados (verifica logs si alguno falló)." >> /home/pi/test_output.log

sleep 5

# --- ACTIVAR ENTORNO VIRTUAL ---
. /home/pi/Desktop/Testdrive/venv/bin/activate

# --- EJECUTAR SCRIPT DE PRUEBA PRINCIPAL ---
echo "Ejecutando union.py" >> /home/pi/test_output.log
python /home/pi/Desktop/Finale/union.py >> /home/pi/test_output.log 2>&1

