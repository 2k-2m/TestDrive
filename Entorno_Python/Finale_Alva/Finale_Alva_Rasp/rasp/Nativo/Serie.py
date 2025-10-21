#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import signal
import itertools
import subprocess
from datetime import datetime
from gnettrack import iniciar_logs

# ============================
# Configuración de rutas
# ============================
CSV_DIR = "/home/pi/Desktop/Finale_Alva/Nativo/Data"
STOP_FLAG = "/home/pi/Desktop/Finale_Alva/pids/STOP.flag"

# Asegura directorios necesarios
os.makedirs(CSV_DIR, exist_ok=True)
os.makedirs(os.path.dirname(STOP_FLAG), exist_ok=True)

# (Opcional pero recomendado) Limpia STOP.flag viejo al arrancar
try:
    os.remove(STOP_FLAG)
except FileNotFoundError:
    pass

# Timestamp de SESIÓN (un CSV por toda la corrida del launcher)
SESSION_TS = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

CSV_INSTAGRAM = os.path.join(CSV_DIR, f"Instagram_Data_{SESSION_TS}.csv")
CSV_FACEBOOK  = os.path.join(CSV_DIR, f"Facebook_Data_{SESSION_TS}.csv")

# Orden fijo (Instagram -> Facebook)
SCRIPTS = [
    "/home/pi/Desktop/Finale_Alva/Nativo/instagram.py",
    "/home/pi/Desktop/Finale_Alva/Nativo/facebook.py",
]

# ============================
# Señales + STOP FLAG
# ============================
detener = False

def _on_signal(sig, frame):
    """Handler de señales: marca detener=True y deja STOP.flag (latch)."""
    global detener
    detener = True
    try:
        os.makedirs(os.path.dirname(STOP_FLAG), exist_ok=True)
        with open(STOP_FLAG, "w") as _:
            pass
    except Exception:
        pass
    print(f"[INFO] Señal {sig} recibida → detención con gracia...")

signal.signal(signal.SIGTERM, _on_signal)
signal.signal(signal.SIGINT,  _on_signal)

def should_stop():
    """True si hay señal o si existe STOP.flag."""
    return detener or os.path.exists(STOP_FLAG)

# ============================
# Helpers de proceso
# ============================
def _terminate_process_tree(proc, name, term_timeout=10.0):
    """
    Envía SIGTERM al grupo del hijo (setsid) y espera; si no sale a tiempo, SIGKILL.
    """
    if proc is None:
        return
    try:
        if proc.poll() is not None:
            return  # ya terminó
    except Exception:
        pass

    # Intenta obtener el PGID (grupo de procesos)
    try:
        pgid = os.getpgid(proc.pid)
    except Exception:
        pgid = None

    # SIGTERM
    try:
        if pgid is not None:
            os.killpg(pgid, signal.SIGTERM)
        else:
            proc.terminate()
        print(f"[INFO] SIGTERM → {name} (pid={proc.pid})")
    except Exception as e:
        print(f"[WARN] No se pudo SIGTERM {name}: {e}")

    t0 = time.time()
    while proc.poll() is None and (time.time() - t0) < term_timeout:
        time.sleep(0.2)

    # SIGKILL si hace falta
    if proc.poll() is None:
        try:
            if pgid is not None:
                os.killpg(pgid, signal.SIGKILL)
            else:
                proc.kill()
            print(f"[WARN] {name} no salió a tiempo → SIGKILL")
        except Exception as e:
            print(f"[WARN] No se pudo SIGKILL {name}: {e}")

def _run_one(script_path, env=None):
    """
    Lanza un hijo en su propio grupo (setsid), y lo detiene con gracia si
    llega Stop (señal o STOP.flag) mientras corre.
    """
    py = sys.executable or "python3"
    if env is None:
        env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    # Barrera: si ya hay STOP, no lanzamos este script
    if should_stop():
        print(f"[INFO] Stop detectado antes de lanzar {os.path.basename(script_path)}. No se lanzará.")
        return 130

    # Lanzar el hijo en su propio grupo para poder matarlo con killpg
    proc = subprocess.Popen(
        [py, "-u", script_path],
        env=env,
        preexec_fn=os.setsid,   # grupo propio (solo POSIX/Linux)
        stdin=None, stdout=None, stderr=None,
        close_fds=True,
    )
    name = os.path.basename(script_path)
    print(f"[INFO] Lanzado {name} (pid={proc.pid})")

    rc = None
    try:
        while True:
            rc = proc.poll()
            if rc is not None:
                print(f"[INFO] {name} finalizó (rc={rc})")
                break

            # Chequeo frecuente: si llegó Stop, apaga con gracia
            if should_stop():
                print(f"[INFO] Stop detectado → cerrar {name} con gracia...")
                _terminate_process_tree(proc, name, term_timeout=10.0)
                rc = proc.poll()
                if rc is None:
                    rc = -9
                break

            time.sleep(0.2)
    finally:
        # Si aún sigue, forzamos cierre
        if proc.poll() is None:
            _terminate_process_tree(proc, name, term_timeout=4.0)

    return rc if rc is not None else 0

# ============================
# Bucle principal
# ============================
def run_scripts_in_sequence(scripts, iterations=0, stop_on_error=False, delay_between=0.0):
    """
    iterations: 0 = infinito; >0 = N vueltas completas.
    stop_on_error: corta si un hijo devuelve rc != 0.
    delay_between: pausa (s) entre scripts de la misma iteración.
    """
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    # Exporta las rutas CSV para que las lean los hijos
    env["CSV_INSTAGRAM_PATH"] = CSV_INSTAGRAM
    env["CSV_FACEBOOK_PATH"]  = CSV_FACEBOOK

    iter_source = range(iterations) if iterations > 0 else itertools.count()

    try:
        for i in iter_source:
            # Si ya pediste Stop, ni arrancamos la vuelta
            if should_stop():
                print("[INFO] Stop detectado antes de iniciar la iteración. Saliendo.")
                break

            print(f"\n--- Iteración {i+1} ---")
            for script in scripts:
                # Barrera entre scripts: no lanzamos si llegó Stop
                if should_stop():
                    print("[INFO] Stop detectado entre scripts. No se lanzará el siguiente.")
                    return 0

                print(f"→ Ejecutando: {script}")
                # Re-chequeo tardío por si el Stop entra “en el filo”
                if should_stop():
                    print("[INFO] Stop detectado justo antes de lanzar. Saliendo.")
                    return 0

                rc = _run_one(script, env=env)

                if rc != 0:
                    print(f"[WARN] {os.path.basename(script)} → rc={rc}")
                    if stop_on_error:
                        print("[INFO] stop_on_error=True → terminar Serie.py")
                        return rc

                # Si apretaste Stop mientras corría el hijo, al volver NO arrancamos el siguiente
                if should_stop():
                    print("[INFO] Stop detectado tras finalizar el script actual. Saliendo.")
                    return 0

                # Pequeño gap entre scripts (sin bloquear Stop)
                if delay_between > 0:
                    t = float(delay_between)
                    end = time.time() + t
                    while time.time() < end:
                        if should_stop():
                            print("[INFO] Stop durante gap. Saliendo.")
                            return 0
                        time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n[INFO] Serie.py interrumpido (KeyboardInterrupt).")

    return 0

udid = "R58MA32XQQW"
portServer="4723"
# ============================
# Entrada
# ============================
if __name__ == "__main__":
    iniciar_logs(
        udid=udid,
        server_url=f"http://127.0.0.1:{portServer}",
        start_data_sequence=False,
        background_after=True,
        caps_overrides={"systemPort": 8242, "mjpegServerPort": 7817}
    )
    sys.exit(run_scripts_in_sequence(SCRIPTS, iterations=0, stop_on_error=False, delay_between=7))
