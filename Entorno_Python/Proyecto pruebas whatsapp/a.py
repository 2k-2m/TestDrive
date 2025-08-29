# check_loc_legacy.py
import subprocess, re, time, sys

UDIDS = sys.argv[1:] or ["6NUDU18529000033", "6NU7N18614004267"]

def adb(u, *args, t=8):
    return subprocess.check_output(["adb","-s",u,*args], encoding="utf-8", errors="ignore", timeout=t)

def loc_enabled_legacy(u):
    # Android viejos: secure location_mode (0=off, 1=GPS, 2=Network, 3=High accuracy)
    for scope in ("secure","global"):
        try:
            v = adb(u,"shell","settings","get",scope,"location_mode").strip()
            if v.isdigit():
                return v != "0", int(v)
        except Exception:
            pass
    # Último recurso: providers_allowed no vacío = encendido
    try:
        prov = adb(u,"shell","settings","get","secure","location_providers_allowed").strip()
        return bool(prov), None
    except Exception:
        return False, None

PATS = [
    re.compile(r'(?P<p>gps|fused|network)\s*:\s*Location\[[^\s]+\s+([-\d.]+)\s*,\s*([-\d.]+)', re.I),
    re.compile(r'Location\[\s*(?P<p>gps|fused|network)\s+([-\d.]+)\s*,\s*([-\d.]+)', re.I),
    re.compile(r'mLast(?:Known)?Location\s*=\s*Location\[\s*(?P<p>gps|fused|network)\s+([-\d.]+)\s*,\s*([-\d.]+)', re.I),
]

def parse_any_latlon(txt):
    found = {}
    for pat in PATS:
        for m in pat.finditer(txt):
            p = (m.group('p') or "").lower()
            lat, lon = m.group(2), m.group(3)
            if p and p not in found and lat and lon and lat.lower()!="nan" and lon.lower()!="nan":
                found[p] = (lat, lon)
    for pref in ("fused","gps","network"):
        if pref in found:
            return pref, found[pref], found
    return None, None, found

def seed_maps(u, wait_s=15):
    try:
        adb(u,"shell","am","start","-a","android.intent.action.VIEW","-d","geo:0,0?q=.")
        time.sleep(wait_s)
        adb(u,"shell","input","keyevent","4")
    except Exception:
        pass

def run(u):
    print(f"\n=== {u} ===")
    on, mode = loc_enabled_legacy(u)
    print(f"Location enabled: {on}  (mode={mode if mode is not None else 'n/a'})")
    if not on:
        print(">> Enciende la ubicación en el teléfono (Alta precisión).")
        return
    txt = adb(u,"shell","dumpsys","location")
    prov, coords, all_found = parse_any_latlon(txt)
    if coords:
        print("Found:", all_found); print(f"Sugerido: {prov} → {coords[0]},{coords[1]}"); return
    print(">> Sembrando con Maps...")
    seed_maps(u)
    txt = adb(u,"shell","dumpsys","location")
    prov, coords, all_found = parse_any_latlon(txt)
    if coords:
        print("Found:", all_found); print(f"Sugerido: {prov} → {coords[0]},{coords[1]}"); return
    print(">> Aún sin LKL. Revisa que Ubicación esté ON y que Maps tenga permiso de ubicación.")
import subprocess, re

def obtener_gps_via_logcat(udid, timeout_s=4):
    """
    Lee el último fix emitido por tu GpsService en logcat (tag VAST_GPS).
    Formato esperado de línea:  "I/VAST_GPS: -17.38,-66.15"
    """
    try:
        out = subprocess.check_output(
            ["adb", "-s", udid, "logcat", "-d", "-s", "VAST_GPS:I"],
            encoding="utf-8", errors="ignore", timeout=timeout_s
        )
        # Buscar la última "lat,lon"
        last = None
        for line in out.splitlines():
            m = re.search(r'VAST_GPS:\s*([-\d.]+)\s*,\s*([-\d.]+)', line)
            if m:
                last = (m.group(1), m.group(2))
        if last:
            return last
    except Exception:
        pass
    return ("n/a", "n/a")

if __name__ == "__main__":
    for u in UDIDS:
        run(u)
        lat, lon = obtener_gps_via_logcat("6NUDU18529000033")
        print("A:", lat, lon)
        lat, lon = obtener_gps_via_logcat("6NU7N18614004267")
        print("B:", lat, lon)
