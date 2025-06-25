import os
import subprocess
import pandas as pd
import re
from datetime import datetime

# Ruta de destino en PC
DESTINO_PC = r'C:\Users\Viva\3D Objects\G_net'

# Ruta en el celular
RUTA_CELULAR = '/sdcard/G-NetTrack_Pro_Logs'

# Detectar carpetas por patrón de fecha
PATRON_FECHA = re.compile(r'_(\d{4}\.\d{2}\.\d{2}_\d{2}\.\d{2}\.\d{2})$')

def extraer_fecha(nombre):
    match = PATRON_FECHA.search(nombre)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y.%m.%d_%H.%M.%S")
        except:
            return None
    return None

def obtener_ultima_carpeta():
    resultado = subprocess.run(['adb', 'shell', f'ls {RUTA_CELULAR}'], capture_output=True, text=True)
    carpetas = resultado.stdout.strip().splitlines()

    # Filtrar por nombre válido y fecha
    fechadas = []
    for nombre in carpetas:
        fecha = extraer_fecha(nombre)
        if fecha:
            fechadas.append((fecha, nombre))

    if not fechadas:
        print("❌ No se encontraron carpetas con nombre de fecha.")
        return None

    ultima = sorted(fechadas, reverse=True)[0][1]
    return ultima

def copiar_desde_adb(nombre_carpeta):
    ruta_remota = f'{RUTA_CELULAR}/{nombre_carpeta}'
    subprocess.run(['adb', 'pull', ruta_remota, DESTINO_PC])
    ruta_local = os.path.join(DESTINO_PC, nombre_carpeta)
    print(f"📥 Copiando {ruta_remota} → {ruta_local}")
    return ruta_local

def procesar_txt_a_csv(ruta_archivo):
    with open(ruta_archivo, 'r', encoding='utf-8', errors='ignore') as f:
        linea = f.readline()

    if ',' in linea:
        sep = ','
    elif ';' in linea:
        sep = ';'
    elif '\t' in linea:
        sep = '\t'
    else:
        sep = None

    try:
        df = pd.read_csv(ruta_archivo, sep=sep)
    except Exception as e:
        print(f"⚠️ Error leyendo {ruta_archivo}: {e}")
        return

    ruta_csv = ruta_archivo.replace('.txt', '.csv')
    ruta_xlsx = ruta_archivo.replace('.txt', '.xlsx')
    df.to_excel(ruta_xlsx, index=False)
    subprocess.run(['start', 'excel', ruta_xlsx], shell=True)

def main():
    ultima = obtener_ultima_carpeta()
    if not ultima:
        return

    ruta_local = copiar_desde_adb(ultima)

    for archivo in os.listdir(ruta_local):
        if archivo.endswith('.txt'):
            procesar_txt_a_csv(os.path.join(ruta_local, archivo))

if __name__ == '__main__':
    main()
