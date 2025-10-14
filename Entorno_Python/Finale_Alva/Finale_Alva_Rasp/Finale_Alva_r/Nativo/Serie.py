#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import signal
import itertools
import subprocess

# Orden fijo (Instagram -> Facebook)
SCRIPTS = [
    "/home/pi/Desktop/Finale_Alva/Nativo/instagram.py",
    "/home/pi/Desktop/Finale_Alva/Nativo/facebook.py",
]

# ========== Señales + STOP FLAG ==========
detener = False
STOP_FLAG = "/home/pi/Desktop/Finale_Alva/pids/STOP.flag"  # la crea el launcher al hacer stop

def _on_signal(sig, frame):
    global detener
    detener = True
    print(f"[INFO] Señal {sig} recibida → detención con gracia...")

signal.signal(signal.SIGTERM, _on_signal)
signal.signal(signal.SIGINT,  _on_signal)

def should_stop():
    """True si hay señal o si el launcher tocó el STOP.flag."""
    return detener or os.path.exists(STOP_FLAG)

# ========== Helpers de proceso ==========
def _terminate_process_tree(proc, name, term_timeout=10.0):
    """SIGTERM al grupo del hijo, espera; si no sale, SIGKILL."""
    if proc is None:
        return
    try:
        if proc.poll() is not None:
            return  # ya terminó
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

    proc = subprocess.Popen(
        [py, "-u", script_path],
        env=env,
        preexec_fn=os.setsid,   # grupo propio
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
        if proc.poll() is None:
            _terminate_process_tree(proc, name, term_timeout=4.0)

    return rc if rc is not None else 0

# ========== Bucle principal ==========
def run_scripts_in_sequence(scripts, iterations=0, stop_on_error=False, delay_between=0.0):
    """
    iterations: 0 = infinito; >0 = N vueltas completas.
    stop_on_error: corta si un hijo devuelve rc != 0.
    delay_between: pausa (s) entre scripts de la misma iteración.
    """
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    iter_source = range(iterations) if iterations > 0 else itertools.count()

    try:
        for i in iter_source:
            # Si ya pediste Stop, ni arrancamos la vuelta
            if should_stop():
                print("[INFO] Stop detectado antes de iniciar la iteración. Saliendo.")
                break

            print(f"\n--- Iteración {i+1} ---")
            for script in scripts:
                # **Barrera**: evita la carrera entre “fin de script” y “arrancar el siguiente”
                if should_stop():
                    print("[INFO] Stop detectado entre scripts. No se lanzará el siguiente.")
                    return 0

                print(f"→ Ejecutando: {script}")
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

if __name__ == "__main__":
    sys.exit(run_scripts_in_sequence(SCRIPTS, iterations=0, stop_on_error=False, delay_between=0))

