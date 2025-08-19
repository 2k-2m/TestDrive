import subprocess
import signal
import os
import sys

def run_all_scripts():
    scripts = [
        "/home/pi/Desktop/Finale/instagram.py",
        "/home/pi/Desktop/Finale/whatsapp.py",
        "/home/pi/Desktop/Finale/facebook.py"
    ]

    procesos = []
    with open("/home/pi/union_children.pid", "w") as f:
        for script in scripts:
            p = subprocess.Popen(["python3", script])
            procesos.append(p)
            f.write(str(p.pid) + "\n")

    try:
        for p in procesos:
            p.wait()
    except KeyboardInterrupt:
        print("[INFO] Detención solicitada. Cerrando procesos...")
        for p in procesos:
            try:
                p.send_signal(signal.SIGTERM)
            except:
                pass
        for p in procesos:
            p.wait()
        sys.exit(0)

if __name__ == "__main__":
    run_all_scripts()

