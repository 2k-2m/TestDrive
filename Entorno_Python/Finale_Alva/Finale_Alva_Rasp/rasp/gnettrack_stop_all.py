#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Detiene los logs de G-NetTrack Pro+ en varios dispositivos y luego
cierra G-NetTrack y apps adicionales por dispositivo.

- Sólo el/los udid listados en WAKE_STRICT_UDIDS usan una secuencia robusta
  para encender pantalla / descartar keyguard antes de foreground.
- El resto hace foreground directo.
- Luego intenta detener_logs() y finalmente hace force-stop de paquetes.

No toca Data Sequence (STOP_DATA_SEQUENCE=False) y deja la app en background.
"""

import os
import sys
import time
import signal
import subprocess
import json
from urllib import request

# ----------------- Import paths (sin duplicar gnettrack.py) -----------------
ROOT = os.path.dirname(os.path.abspath(__file__))
for p in (ROOT, os.path.join(ROOT, "Nativo"), os.path.join(ROOT, "Calls"), os.path.join(ROOT, "Alva_Net")):
    if p not in sys.path:
        sys.path.insert(0, p)

from gnettrack import detener_logs  # tu módulo existente

# -------------------------- Configuración base --------------------------
GNET_PKG = "com.gyokovsolutions.gnettrackproplus"
GNET_ACT = "com.gyokovsolutions.gnettrackproplus.MainActivity"

# (name, udid, server_url, extra_pkgs_to_force_stop)
DEVICES = [
    ("Serie (Nativo)",    "R58MA32XQQW", "http://127.0.0.1:4723",
        ["com.instagram.android", "com.facebook.katana", "com.facebook.lite"]),
    ("Alva (Browser)",    "R58M795NHZF", "http://127.0.0.1:4783",
        ["org.oyealva.stable"]),
    ("Calls (Telefonía)", "RF8MB0G4KTJ", "http://127.0.0.1:4793",
        ["com.samsung.android.dialer", "com.google.android.dialer", "com.android.dialer"]),
]

# A estos UDIDs les aplicamos wake/unlock robusto (incluimos SERIE)
WAKE_STRICT_UDIDS = {"RF8MB0G4KTJ", "R58MA32XQQW"}

STOP_DATA_SEQUENCE = False   # pedido: no tocar Data
BACKGROUND_AFTER   = True

# ----------------------------- Señales -----------------------------
_abort = False
def _on_sig(sig, frame):
    global _abort
    _abort = True
    print(f"[INFO] Señal {sig} recibida, abortando tras la iteración actual...")

signal.signal(signal.SIGINT,  _on_sig)
signal.signal(signal.SIGTERM, _on_sig)

# --------------------------- HTTP helper (cerrar sesiones) ---------------------------
def _close_sessions(server_url: str, timeout=2.5):
    """
    Cierra todas las sesiones activas del servidor Appium indicado.
    Seguro de usar aunque no haya ninguna.
    """
    try:
        with request.urlopen(f"{server_url}/sessions", timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
        sessions = (data.get("value") or [])
        for s in sessions:
            sid = s.get("id") or s.get("sessionId") or s.get("session_id")
            if not sid:
                continue
            req = request.Request(f"{server_url}/session/{sid}", method="DELETE")
            try:
                request.urlopen(req, timeout=timeout).read()
                time.sleep(0.1)
            except Exception as e:
                print(f"[DBG] No se pudo borrar sesión {sid} en {server_url}: {e}")
    except Exception as e:
        print(f"[DBG] _close_sessions({server_url}): {e}")

# --------------------------- Utilidades ADB ---------------------------
def _adb(serial, *args, timeout=8, quiet=False):
    cmd = ["adb", "-s", serial] + list(args)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        if not quiet and res.returncode != 0:
            print(f"[DBG] ADB ERR ({serial}): {' '.join(args)} -> {res.stderr.strip()}")
        return res
    except Exception as e:
        class R: pass
        r = R(); r.returncode = -1; r.stdout = ""; r.stderr = str(e)
        if not quiet:
            print(f"[DBG] ADB EXC ({serial}): {' '.join(args)} -> {e}")
        return r

def _is_awake(serial) -> bool:
    r = _adb(serial, "shell", "dumpsys", "power", timeout=6, quiet=True)
    out = (r.stdout or "").lower()
    return ("minteractive=true" in out) or ("display power: state=on" in out)

def _wake_and_dismiss_keyguard(serial, retries=3):
    for _ in range(retries):
        _adb(serial, "shell", "input", "keyevent", "224", timeout=4, quiet=True)  # wake
        time.sleep(0.2)
        _adb(serial, "shell", "svc", "power", "stayon", "usb", timeout=4, quiet=True)
        _adb(serial, "shell", "wm", "dismiss-keyguard", timeout=4, quiet=True)
        time.sleep(0.1)
        _adb(serial, "shell", "input", "keyevent", "82", timeout=3, quiet=True)   # MENU
        time.sleep(0.1)
        _adb(serial, "shell", "input", "swipe", "500", "1600", "500", "400", "250", timeout=3, quiet=True)
        time.sleep(0.2)
        if _is_awake(serial):
            return True
        time.sleep(0.5)
    return _is_awake(serial)

def bring_gnet_foreground(serial) -> bool:
    _adb(serial, "shell", "input", "keyevent", "3", timeout=3, quiet=True)  # HOME
    time.sleep(0.15)
    r = _adb(
        serial, "shell", "am", "start",
        "-n", f"{GNET_PKG}/{GNET_ACT}",
        "-a", "android.intent.action.MAIN",
        "-c", "android.intent.category.LAUNCHER",
        timeout=6, quiet=True
    )
    ok = (r.returncode == 0)
    if ok:
        print(f"[INFO] G-NetTrack al frente en {serial}.")
    else:
        print(f"[WARN] No se pudo foreground G-NetTrack en {serial}: {r.stderr.strip()}")
    time.sleep(0.6)
    return ok

def cerrar_apps(paquetes, serial):
    for paquete in paquetes:
        try:
            subprocess.run(
                ['adb', '-s', serial, 'shell', 'am', 'force-stop', paquete],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
            )
        except Exception as e:
            print(f"[WARN] No se pudo force-stop {paquete} en {serial}: {e}")
    if paquetes:
        print(f"[INFO] Apps {paquetes} cerradas en {serial}.")

# ------------------------------- Main -------------------------------
def main() -> int:
    errors = 0
    for name, udid, server_url, extra_pkgs in DEVICES:
        if _abort:
            break

        print(f"[INFO] Deteniendo G-NetTrack en {name} (UDID={udid}) vía {server_url}...")

        # 1) Foreground (y wake/unlock robusto si aplica)
        if udid in WAKE_STRICT_UDIDS:
            if not _is_awake(udid):
                ok_wake = _wake_and_dismiss_keyguard(udid, retries=4)
                if not ok_wake:
                    print(f"[WARN] {name}: no se pudo asegurar pantalla despierta/descubierta.")
        fg_ok = bring_gnet_foreground(udid)

        # 2) Intentar detener el log si hay UI al frente
        if fg_ok:
            try:
                ok = detener_logs(
                    udid=udid,
                    server_url=server_url,
                    stop_data_sequence=STOP_DATA_SEQUENCE,
                    background_after=BACKGROUND_AFTER,
                )
                if ok:
                    print(f"[OK] {name}: log detenido correctamente.")
                else:
                    print(f"[WARN] {name}: detener_logs devolvió False.")
                    errors += 1
            except Exception as e:
                print(f"[WARN] {name}: excepción al detener logs -> {e}")
                errors += 1
            finally:
                _close_sessions(server_url)  # limpieza crítica
        else:
            print(f"[WARN] {name}: no se pudo llevar a foreground; saltamos detener_logs().")
            _close_sessions(server_url)     # best effort

        # 3) Limpieza final: force-stop de G-NetTrack + extras
        pkgs = [GNET_PKG] + list(dict.fromkeys(extra_pkgs))
        cerrar_apps(pkgs, udid)
        time.sleep(0.2)

    if _abort:
        print("[INFO] Abortado por señal.")
        return 130
    return 0 if errors == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
