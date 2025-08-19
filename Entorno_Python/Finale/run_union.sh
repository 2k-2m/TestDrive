#!/bin/bash

# Ejecutar Union_prueba1.py en segundo plano y guardar su PID
source /home/pi/Desktop/Testdrive/venv/bin/activate
python /home/pi/Desktop/Finale/union.py >> /home/pi/test_output.log 2>&1 &
echo $! > /home/viva/union.pid