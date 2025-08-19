#!/bin/bash
set -u -o pipefail

# --- INICIAR GPS (idempotente) ---
adb -s RF8MB0G4KTJ shell am start-foreground-service -n viva.vast/.GpsService || true
adb -s R58MA32XQQW  shell am start-foreground-service -n viva.vast/.GpsService || true
adb -s R58M795NHZF shell am start-foreground-service -n viva.vast/.GpsService || true

# --- (opcional) liberar systemPorts y uiautomator2 server en devices ---
sudo lsof -ti tcp:8200,8201,8202 | xargs -r sudo kill -9
for ud in RF8MB0G4KTJ R58MA32XQQW R58M795NHZF; do
  adb -s "$ud" shell am force-stop io.appium.uiautomator2.server io.appium.uiautomator2.server.test || true
done

# --- ACTIVAR VENV ---
source /home/pi/Desktop/Testdrive/venv/bin/activate

# --- EJECUTAR UNION EN SEGUNDO PLANO ---
python -u /home/pi/Desktop/Finale/union.py >> /home/pi/test_output.log 2>&1 &
echo $! > /home/pi/union.pid
echo "[INFO] union.py lanzado (PID $(cat /home/pi/union.pid))"

