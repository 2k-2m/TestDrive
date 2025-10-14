import subprocess
import signal
import os
import sys
import time
import itertools

# Usa una LISTA (respeta el orden). En Windows, mejor raw strings por las barras invertidas y espacios.
SCRIPTS = [
    r"C:\Users\Viva\Desktop\Finale vs Alva\Nativo\instagram.py",
    r"C:\Users\Viva\Desktop\Finale vs Alva\Nativo\facebook.py",
]

def run_scripts_in_sequence(scripts, iterations=1, stop_on_error=False, delay_between=0):
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    # Rango de iteraciones (infinito si iterations == 0)
    iter_source = range(iterations) if iterations > 0 else itertools.count()

    try:
        for i in iter_source:
            print(f"\n--- Iteración {i+1} ---")
            for script in scripts:
                print(f"→ Ejecutando: {script}")
                # sys.executable asegura usar el mismo intérprete en cualquier OS
                result = subprocess.run([sys.executable, "-u", script], env=env)
                if result.returncode != 0:
                    print(f"[WARN] {os.path.basename(script)} terminó con código {result.returncode}")
                    if stop_on_error:
                        print("[INFO] Deteniendo por error (stop_on_error=True).")
                        return result.returncode
                if delay_between > 0:
                    time.sleep(delay_between)
    except KeyboardInterrupt:
        print("\n[INFO] Detenido por el usuario (Ctrl+C).")
    return 0

if __name__ == "__main__":
    # Ejemplos de uso:
    # 1) Ejecutar una sola vez (instagram -> facebook) y terminar:
    # run_scripts_in_sequence(SCRIPTS, iterations=1)

    # 2) Ejecutar en bucle infinito hasta Ctrl+C:
    # run_scripts_in_sequence(SCRIPTS, iterations=0)

    # 3) Detener si algún script falla y esperar 2s entre scripts:
    # run_scripts_in_sequence(SCRIPTS, iterations=0, stop_on_error=True, delay_between=2)

    run_scripts_in_sequence(SCRIPTS, iterations=0)
