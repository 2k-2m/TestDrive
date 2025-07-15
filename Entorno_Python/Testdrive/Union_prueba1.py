from multiprocessing import Process
import os
import signal
import sys

BASE_PATH = "/home/pi/Desktop/Testdrive"

def run_script(name):
    full_path = os.path.join(BASE_PATH, name)
    os.system(f'python {full_path}')

if __name__ == "__main__":
    procesos = [
        Process(target=run_script, args=("Instagram_3.py",)),
        Process(target=run_script, args=("Whatsapp_2.py",)),
        Process(target=run_script, args=("Facebook_2.py",)),
    ]

    try:
        for p in procesos:
            p.start()
        for p in procesos:
            p.join()
    except KeyboardInterrupt:
        print("\n[INFO] Detención solicitada. Cerrando procesos...")
        for p in procesos:
            p.terminate()
        for p in procesos:
            p.join()
        sys.exit(0)
