from multiprocessing import Process
import os

def run_script(path):
    os.system(f'python {path}')

if __name__ == "__main__":
    procesos = [
        Process(target=run_script, args=("Facebook_2.py",)),
        Process(target=run_script, args=("Whatsapp_2.py",)),  # corregido
        Process(target=run_script, args=("Instagram_2.py",)), 
    ]
    for p in procesos:
        p.start()
    for p in procesos:
        p.join()
 