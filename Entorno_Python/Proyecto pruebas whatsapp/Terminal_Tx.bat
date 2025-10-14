@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

:: Ruta del intérprete de Python
set "PY=C:\Users\Viva\AppData\Local\Programs\Python\Python313\python.exe"

:: Rutas de los scripts
set "SCRIPT_ENTEL=C:\Users\Viva\Desktop\Split Llamadas\Entel\llamada_CSV_Split_Entel.py"
set "SCRIPT_VIVA=C:\Users\Viva\Desktop\Split Llamadas\Viva\llamada_CSV_Split_Viva.py"
set "SCRIPT_TIGO=C:\Users\Viva\Desktop\Split Llamadas\Tigo\llamada_CSV_Split_Tigo.py"

set count=0
for /f "skip=1 tokens=1" %%i in ('adb devices') do (
    if not "%%i"=="" (
        set /a count+=1
    )
)

if !count! EQU 3 (
    echo [OK] Se detectaron 3 dispositivos. Iniciando servicios...

    adb -s 6NUDU18529000033 shell am start-foreground-service -n viva.vast/.GpsService
    adb -s 6NUDU18529000124 shell am start-foreground-service -n viva.vast/.GpsService
    adb -s 6NUDU18529000190 shell am start-foreground-service -n viva.vast/.GpsService

    echo Iniciando Appium...
    start "Appium 4723" cmd /k appium --relaxed-security -p 4723
    start "Appium 4733" cmd /k appium --relaxed-security -p 4733
    start "Appium 4743" cmd /k appium --relaxed-security -p 4743

    timeout /t 5 /nobreak >nul

    echo Ejecutando scripts de Python...
    start "" "%PY%" "%SCRIPT_ENTEL%"
    start "" "%PY%" "%SCRIPT_VIVA%"
    start "" "%PY%" "%SCRIPT_TIGO%"
) else (
    echo [ERROR] Se detectaron !count! dispositivos. Se requieren exactamente 3.
)

endlocal
