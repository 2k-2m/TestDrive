# -*- coding: utf-8 -*-


import os, subprocess, re, time
from datetime import datetime
from pathlib import Path

EXCEL = False
# Config (ajusta si cambias de equipo o rutas)
UDID = "6NU7N18614004267"  # usa el mismo de tu automatización
RUTA_CELULAR = "/sdcard/G-NetTrack_Pro_Logs"
DESTINO_PC = Path("/home/jetson/Desktop/Finale_Alva/Whats/Viva")
# Patrón de fecha en el nombre de carpeta: ..._YYYY.MM.DD_HH.MM.SS
PATRON_FECHA = re.compile(r'_(\d{4}\.\d{2}\.\d{2}_\d{2}\.\d{2}\.\d{2})$')
def run_adb(args, text=True, check=True):
    cmd = ["adb", "-s", UDID] + args
    res = subprocess.run(cmd, capture_output=True, text=text)
    if check and res.returncode != 0:
        raise RuntimeError(f"ADB fallo: {' '.join(cmd)}\nSTDERR: {res.stderr}")
    return res.stdout if text else res

def extraer_fecha(nombre):
    m = PATRON_FECHA.search(nombre)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y.%m.%d_%H.%M.%S")
    except:
        return None

def listar_directorios_en(ruta_remota):
    out = run_adb(["shell", f"ls -1 {ruta_remota}"], text=True, check=False)
    if not out.strip():
        return []
    return [x.strip() for x in out.splitlines() if x.strip() and "No such" not in x]

def obtener_ultima_carpeta():
    carpetas = listar_directorios_en(RUTA_CELULAR)
    candidatas = []
    for nombre in carpetas:
        fecha = extraer_fecha(nombre)
        if fecha:
            candidatas.append((fecha, nombre))
    if not candidatas:
        print("❌ No se encontraron carpetas con patrón de fecha en el teléfono.")
        return None
    candidatas.sort(reverse=True, key=lambda x: x[0])
    return candidatas[0][1]

def esperar_archivos_estables(ruta_remota_carpeta, intentos=5, espera=1.0):
    """Verifica que los .txt no cambian de tamaño entre sondeos (evita copiar mientras se escriben)."""
    def tamanos():
        out = run_adb(["shell", f'ls -l "{ruta_remota_carpeta}"'], text=True, check=False)
        sizes = {}
        for line in out.splitlines():
            parts = line.split()
            if len(parts) < 5 or not parts[0].startswith("-"):
                continue
            try:
                size = int(parts[4]); name = parts[-1]
                if name.endswith(".txt"):
                    sizes[name] = size
            except:
                pass
        return sizes

    prev = tamanos()
    for _ in range(intentos):
        time.sleep(espera)
        cur = tamanos()
        if cur == prev:
            return True
        prev = cur
    return False

def copiar_carpeta_logs(nombre_carpeta):
    DESTINO_PC.mkdir(parents=True, exist_ok=True)
    ruta_remota = f"{RUTA_CELULAR}/{nombre_carpeta}"

    try:
        estable = esperar_archivos_estables(ruta_remota)
        if not estable:
            print("Archivos posiblemente en escritura; realizando copia igualmente.")
    except Exception as e:
        print(f"No se pudo verificar estabilidad: {e}")

    print(f"📥 adb pull {ruta_remota}  →  {DESTINO_PC}")
    run_adb(["pull", ruta_remota, str(DESTINO_PC)], text=True, check=True)
    ruta_local = DESTINO_PC / nombre_carpeta
    print(f"Carpeta copiada en: {ruta_local}")
    return ruta_local

def extraer_logs_gnettrack():
    nombre = obtener_ultima_carpeta()
    if not nombre:
        return None
    ruta_local = copiar_carpeta_logs(nombre)

    # Si algún día activas EXCEL=True, aquí harías conversiones.
    if EXCEL:
        print("EXCEL=True: aquí iría la conversión opcional (desactivada por ahora).")

    return ruta_local

__all__ = ["EXCEL", "UDID", "RUTA_CELULAR", "DESTINO_PC",
           "extraer_logs_gnettrack", "obtener_ultima_carpeta", "copiar_carpeta_logs"]