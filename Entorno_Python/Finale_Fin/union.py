import subprocess
import signal
import os
import sys

LOGS = {
    "/home/pi/Desktop/Finale/instagram.py": "/home/pi/instagram.log",
    "/home/pi/Desktop/Finale/whatsapp.py":  "/home/pi/whatsapp.log",
    "/home/pi/Desktop/Finale/facebook.py":  "/home/pi/facebook.log",
}

def run_all_scripts():
    procesos = []  # [(Popen, file_handle), ...]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"  # asegura logs al instante

    # guardar PIDs de hijos
    with open("/home/pi/union_children.pid", "w") as pf:
        for script, logfile in LOGS.items():
            # apertura line-buffered (buffering=1) + unbuffered del intérprete (-u)
            logf = open(logfile, "a", buffering=1)
            p = subprocess.Popen(
                ["python3", "-u", script],
                stdout=logf,
                stderr=subprocess.STDOUT,
                env=env
            )
            procesos.append((p, logf))
            pf.write(str(p.pid) + "\n")

    try:
        # esperar a que terminen (si uno cae, seguimos esperando a los demás)
        for p, _ in procesos:
            p.wait()
    except KeyboardInterrupt:
        print("[INFO] Detención solicitada. Cerrando procesos...")
        for p, _ in procesos:
            try:
                p.send_signal(signal.SIGTERM)
            except Exception:
                pass
        for p, _ in procesos:
            try:
                p.wait(timeout=5)
            except Exception:
                pass
        sys.exit(0)
    finally:
        # cerrar archivos de log
        for _, logf in procesos:
            try:
                logf.close()
            except Exception:
                pass

if __name__ == "__main__":
    run_all_scripts()

