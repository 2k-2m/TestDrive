#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
adb_pcapdroid_debug.py
Lee el PCAP en vivo desde PCAPdroid (HTTP exporter) a través de ADB forward y
lo imprime en consola con TShark sin filtros (-V -x). Opcionalmente guarda a .pcap.

Requisitos:
  - adb en PATH
  - TShark instalado (wireshark/tshark)
  - requests (pip install requests) o usa la opción --no-http y curl (ver notas)

Uso típico:
  1) En el teléfono: PCAPdroid -> Dump mode = HTTP exporter (puerto 8080) -> Start
  2) En el PC:
       python adb_pcapdroid_debug.py --port 8080 --save pcapdroid_dump.pcap
     (o sin --save si no quieres archivo)
"""

import os
import sys
import time
import argparse
import shutil
import subprocess
from threading import Event

try:
    import requests
except ImportError:
    requests = None

def which_tshark():
    cand = (
        os.environ.get("TSHARK_PATH")
        or shutil.which("tshark")
        or r"C:\Program Files\Wireshark\tshark.exe"
    )
    if not cand or not os.path.exists(cand):
        raise RuntimeError("No encuentro 'tshark'. Instala Wireshark/TShark o define TSHARK_PATH.")
    return cand

def adb_forward(port: int):
    adb = shutil.which("adb") or "adb"
    try:
        # Crea el forward PC:port -> PHONE:port
        subprocess.check_call([adb, "forward", f"tcp:{port}", f"tcp:{port}"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        print(f"[adb] forward tcp:{port} -> tcp:{port} OK")
    except subprocess.CalledProcessError as e:
        print("[adb] Error creando forward. ¿adb instalado/dispositivo autorizado? Detalle:", e)
        sys.exit(1)

def start_tshark(tshark_path: str):
    # -r -  : lee desde stdin
    # -l    : salida line-buffered (más “en vivo”)
    # -V -x : decodificación completa y hex dump (sin filtros)
    args = [tshark_path, "-r", "-", "-l", "-V", "-x"]
    # Deja stdout/err a la terminal (heredado) para ver TODO en vivo.
    try:
        p = subprocess.Popen(args, stdin=subprocess.PIPE)
    except Exception as e:
        raise RuntimeError(f"No pude lanzar TShark: {e}")
    return p

def stream_http_to_tshark(url: str, tshark_proc, save_path: str | None, stop_evt: Event):
    if requests is None:
        raise RuntimeError("Falta 'requests'. Instálalo: pip install requests")

    fsave = None
    if save_path:
        fsave = open(save_path, "wb")
        print(f"[i] Guardando copia en: {save_path}")

    try:
        with requests.get(url, stream=True, timeout=5) as r:
            r.raise_for_status()
            print(f"[http] Conectado: {url}")
            total = 0
            for chunk in r.iter_content(16384):
                if stop_evt.is_set():
                    break
                if not chunk:
                    continue
                total += len(chunk)
                # Teear a archivo si corresponde
                if fsave:
                    fsave.write(chunk)
                # Enviar a TShark (stdin binario)
                try:
                    tshark_proc.stdin.write(chunk)
                    tshark_proc.stdin.flush()
                except BrokenPipeError:
                    print("[tshark] stdin cerrado (¿tshark terminó?).")
                    break
            print(f"[http] Flujo finalizado. Bytes totales: {total}")
    finally:
        try:
            if tshark_proc and tshark_proc.stdin:
                tshark_proc.stdin.close()
        except Exception:
            pass
        if fsave:
            fsave.flush()
            fsave.close()

def main():
    ap = argparse.ArgumentParser(description="PCAPdroid → ADB forward → TShark sin filtros (-V -x)")
    ap.add_argument("--port", type=int, default=8080, help="Puerto HTTP exporter en el teléfono (default: 8080)")
    ap.add_argument("--host", default="127.0.0.1", help="Host local (no cambiar, default: 127.0.0.1)")
    ap.add_argument("--save", default="", help="Ruta para guardar copia .pcap (opcional)")
    ap.add_argument("--no-forward", action="store_true", help="No ejecutar 'adb forward' (ya lo hiciste tú).")
    ap.add_argument("--retry", type=int, default=0, help="Reintentos si no conecta aún (seg). 0=sin reintentos")
    args = ap.parse_args()

    url = f"http://{args.host}:{args.port}"

    # ADB forward (si no está desactivado)
    if not args.no_forward:
        adb_forward(args.port)

    tshark_path = which_tshark()
    print(f"[i] TShark: {tshark_path}")
    print(f"[i] Leyendo PCAP en vivo desde: {url}")
    print("[i] Recuerda: en el teléfono, PCAPdroid → Dump mode = HTTP exporter → Start.")

    stop_evt = Event()
    tshark = start_tshark(tshark_path)

    # Loop de conexión con reintentos (por si aún no diste Start)
    t0 = time.time()
    attempt = 0
    while True:
        try:
            stream_http_to_tshark(url, tshark, args.save or None, stop_evt)
            break  # salió normalmente
        except Exception as e:
            attempt += 1
            if args.retry <= 0:
                print(f"[x] Error conectando: {e}")
                break
            if (time.time() - t0) > args.retry:
                print(f"[x] Tiempo de reintento agotado ({args.retry}s). Último error: {e}")
                break
            print(f"[!] Aún no conecta ({e}). Reintentando…")
            time.sleep(1)

    # Intento de cierre ordenado
    try:
        tshark.terminate()
    except Exception:
        pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[ctrl-c] Saliendo…")
