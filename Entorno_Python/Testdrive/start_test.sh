#!/bin/bash

# --- VARIABLES ANDROID ---
export ANDROID_HOME=/home/pi/Android
export ANDROID_SDK_ROOT=/home/pi/Android
export PATH=$PATH:$ANDROID_HOME/platform-tools:/usr/bin
export DISPLAY=:0

# --- DIAGNÓSTICO DE ARRANQUE ---
echo "✅ Script ejecutado a: $(date)" >> /home/pi/start_test_autostart.log

# --- LIBERAR PUERTOS USADOS POR ADB/APPIUM ---
echo "Cerrando procesos en puertos 4723, 4725 y 4727..." >> /home/pi/test_output.log
for port in 4723 4725 4727; do
  pid=$(sudo lsof -ti tcp:$port)
  if [ ! -z "$pid" ]; then
    echo "Matando proceso en puerto $port (PID $pid)..." >> /home/pi/test_output.log
    sudo kill -9 $pid
  fi
done
sleep 2

# --- ESPERAR DISPOSITIVOS ADB ---
echo "Esperando que se conecten 3 dispositivos ADB..." >> /home/pi/test_output.log
while true; do
    total=$(adb devices | grep -w "device" | grep -v "List" | wc -l)
    if [ "$total" -eq 3 ]; then
        echo "✅ Dispositivos detectados correctamente." >> /home/pi/test_output.log
        break
    else
        echo "🔄 Detectados: $total/3. Reintentando..." >> /home/pi/test_output.log
        sleep 2
    fi
done

# --- INICIAR SERVIDORES APPIUM ---
echo "Iniciando servidores Appium..." >> /home/pi/test_output.log
appium --relaxed-security -p 4723 >> /home/pi/appium_4723.log 2>&1 &
sleep 5
appium --relaxed-security -p 4725 >> /home/pi/appium_4725.log 2>&1 &
sleep 5
appium --relaxed-security -p 4727 >> /home/pi/appium_4727.log 2>&1 &
sleep 10
echo "✅ Servidores Appium iniciados." >> /home/pi/test_output.log

# --- ACTIVAR ENTORNO VIRTUAL ---
. /home/pi/Desktop/Testdrive/venv/bin/activate

# --- EJECUTAR SCRIPT DE PRUEBA PRINCIPAL ---
echo "▶️ Ejecutando Union_prueba1.py" >> /home/pi/test_output.log
python /home/pi/Desktop/Testdrive/Union_prueba1.py >> /home/pi/test_output.log 2>&1

