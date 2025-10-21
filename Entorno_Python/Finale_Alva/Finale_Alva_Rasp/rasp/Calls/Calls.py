import os, csv, time, re, signal, argparse, subprocess, unicodedata
from datetime import datetime
from gnettrack import iniciar_logs

# ====== RUTAS / PLAN ======
BASE_DIR = os.path.dirname(__file__)
PLAN_TXT = os.path.join(BASE_DIR, "configuracion.txt")
STOP_FILE = os.path.join(BASE_DIR, "stop.flag")

# ====== CONFIG PREDETERMINADA ======
UDID_A        = "RF8MB0G4KTJ"
APPIUM_URL_A  = "http://127.0.0.1:4793"
SYSTEM_PORT_A = 8220
CONTACTO      = "567"
ROLE_CONFIG   = "both"

# ====== TIMEOUTS / DURACIONES ======
ANSWER_TIMEOUT_S           = 30.0
CALL_START_SETTLE_S        = 0.8
CDR_HOLD_S                 = 30
DROP_GRACE_S               = 2.0
INTERCALL_EXTRA_GAP_S      = 1.5
NOANSWER_HANGUP_GRACE_S    = 0.2
NOANSWER_VERIFY_TIMEOUT_S  = 1.0

# ====== CSV ======
timestamp_pc = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
CSV_HEADER = [
    "App","Device","UDID","Network","Evento","CallID","Contact",
    "Latitude","Longitude","Start","End","Result","Failure","Extra"
]
CSV_HEADER_ALL = [
    "App","Device","UDID","Network","Evento","CallID","Contact",
    "Latitude","Longitude","Start","End","Result","Failure","Extra"
]

class CsvWriter:
    def __init__(self, path, header):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f = open(path, "a", newline="", encoding="utf-8")
        self.w = csv.writer(self.f)
        if os.path.getsize(path) == 0:
            self.w.writerow(header)
    def row(self, cells, checkpoint=False):
        self.w.writerow(cells); self.f.flush()
        if checkpoint:
            try: os.fsync(self.f.fileno())
            except: pass
    def close(self):
        try: self.f.close()
        except: pass

def _sanitize_cell(x):
    s = str(x) if x is not None else ""
    return s.replace(",", " ").replace("\n", " ").replace("\r", " ")

csvw_all = None
csvw_device = None
UDID_A_RUNTIME = None

def csv_init_all():
    global csvw_all
    fn_all = os.path.join(BASE_DIR, f"out/Llamadas_ALL_{timestamp_pc}.csv")
    csvw_all = CsvWriter(fn_all, CSV_HEADER_ALL)

def csv_init_device():
    global csvw_device
    fn = os.path.join(BASE_DIR, f"out/Llamadas_{timestamp_pc}.csv")
    csvw_device = CsvWriter(fn, CSV_HEADER)

def csv_write_device(csvw, evento, call_id, contact,
                     start_dt, end_dt, result, failure="",
                     extra="", app="Phone", checkpoint=False,
                     device_label="A", udid=None,
                     lat="n/a", lon="n/a", network=""):
    if udid is None: udid = UDID_A_RUNTIME

    row_dev = [
        app, device_label, (udid or ""), network, evento, call_id, contact,
        lat, lon,
        start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        result, failure, extra
    ]
    row_dev = [_sanitize_cell(c) if isinstance(c, str) else c for c in row_dev]
    csvw.row(row_dev, checkpoint=checkpoint)

    if csvw_all is not None and udid:
        row_all = [
            app, device_label, udid, network, evento, call_id, contact,
            lat, lon,
            start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            result, failure, extra
        ]
        row_all = [_sanitize_cell(c) if isinstance(c, str) else c for c in row_all]
        csvw_all.row(row_all, checkpoint=checkpoint)

# ====== CLI / SEÑALES ======
def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default=PLAN_TXT)
    ap.add_argument("--udid-a", dest="udid_a", default=None)
    ap.add_argument("--contacto", default=None)
    ap.add_argument("--hold", type=int, default=None)
    ap.add_argument("--tiempo-entre-ciclos", type=float, default=None)
    ap.add_argument("--answer-timeout-s", type=float, default=None)
    ap.add_argument("--appium-url-a", default=None)
    ap.add_argument("--system-port-a", type=int, default=None)
    return ap.parse_args()

detener = False
def manejar_senal(sig, frame):
    global detener
    print("\n[INFO] Terminando con gracia...")
    detener = True
signal.signal(signal.SIGINT, manejar_senal)
signal.signal(signal.SIGTERM, manejar_senal)

def should_stop(): return detener or os.path.exists(STOP_FILE)

def sleep_coop(total_s: float, step_s: float = 0.2) -> bool:
    t = 0.0
    while t < float(total_s):
        if should_stop(): return False
        time.sleep(step_s); t += step_s
    return True

# ====== LOG ======
DEBUG = True
CALL_ID = 0
def log_evt(k: str, when: datetime | None = None, extra: str = ""):
    if not DEBUG: return
    if when is None: when = datetime.now()
    ts = when.strftime("%H:%M:%S")
    print(f"[DBG] {k} @ {ts}{(' | '+extra) if extra else ''}")

# ====== UTILS ======
def wait_until(fn, timeout_s=10.0, interval_s=0.25, cancel_fn=should_stop):
    t0 = time.monotonic()
    while (time.monotonic() - t0) < timeout_s:
        if cancel_fn and cancel_fn(): return False
        try:
            if fn(): return True
        except Exception:
            pass
        time.sleep(interval_s)
    return False

def _norm(s: str) -> str:
    s = (s or "").lower()
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

# ====== ADB CORE (tolerante) ======
def adb(cmd_list, serial=None, timeout=15):
    base = ["adb"]
    if serial: base += ["-s", serial]
    try:
        return subprocess.run(base + cmd_list, text=True, capture_output=True,
                              timeout=timeout, check=False)
    except Exception as e:
        class _Res:
            def __init__(self, stdout, stderr, returncode):
                self.stdout = stdout; self.stderr = stderr; self.returncode = returncode
        return _Res(stdout="", stderr=str(e), returncode=-1)

# ====== ESTADOS TELEFONÍA/TELECOM ======
_TEL_STATE_RE = re.compile(r"\bmCallState\s*=\s*(\d+)\b")
def _telephony_call_state(serial: str) -> int:
    res = adb(["shell", "dumpsys", "telephony.registry"], serial=serial, timeout=8)
    out = res.stdout or ""
    if res.returncode != 0 and should_stop():
        return 0
    matches = list(_TEL_STATE_RE.finditer(out))
    if not matches: return -1
    try: return int(matches[-1].group(1))
    except: return -1

def is_call_idle(serial: str) -> bool:
    return _telephony_call_state(serial) == 0

_PHASE_RE = re.compile(r"\bSTATE\s*:\s*(DIALING|ALERTING|RINGING|ACTIVE)\b", re.I)
def telecom_phase(serial: str) -> str:
    res = adb(["shell","dumpsys","telecom"], serial=serial, timeout=8)
    out = res.stdout or ""
    if not out: return "UNKNOWN"
    phases = _PHASE_RE.findall(out)
    return (phases[-1].upper() if phases else "UNKNOWN")

# ====== MARCAR / COLGAR ======
def dial_via_adb(serial: str, number: str, pause_before_press=0.5):
    adb(["shell","am","start","-a","android.intent.action.DIAL","-d", f"tel:{number}"], serial=serial)
    time.sleep(max(0.1, float(pause_before_press)))
    adb(["shell","input","keyevent","5"], serial=serial)

def force_hangup_and_wait_idle(serial: str, grace_s: float = 2.0, verify_timeout_s: float = 8.0):
    try:
        try:
            adb(["shell","cmd","telecom","end-call"], serial=serial, timeout=5)
        except Exception:
            adb(["shell","input","keyevent","6"], serial=serial, timeout=5)
    except Exception:
        pass
    time.sleep(grace_s)
    if not wait_until(lambda: is_call_idle(serial), timeout_s=verify_timeout_s, interval_s=0.3):
        try: adb(["shell","input","keyevent","6"], serial=serial, timeout=5)
        except Exception: pass
        time.sleep(1.0)
        _ = wait_until(lambda: is_call_idle(serial), timeout_s=verify_timeout_s, interval_s=0.3)

def force_hangup_fast(serial: str):
    adb(["shell","cmd","telecom","end-call"], serial=serial, timeout=3)
    time.sleep(0.1)
    adb(["shell","input","keyevent","6"], serial=serial, timeout=3)
    time.sleep(0.1)
    adb(["shell","input","keyevent","6"], serial=serial, timeout=3)
    _ = wait_until(lambda: is_call_idle(serial), timeout_s=1.5, interval_s=0.2)

def ensure_idle_before_dial(serial: str, max_wait_s: float = 5.0):
    if not wait_until(lambda: is_call_idle(serial), timeout_s=max_wait_s, interval_s=0.25):
        force_hangup_and_wait_idle(serial, grace_s=1.0, verify_timeout_s=5.0)

# ====== GPS / RED / HORA (ADB) ======
def obtener_gps(serial: str):
    res = adb(["shell", "dumpsys", "location"], serial=serial, timeout=10)
    out = res.stdout or ""
    m = re.search(r'gps:\s+Location\[gps\s+([-\d\.]+),\s*([-\d\.]+)', out, re.I)
    if m: return str(m.group(1)), str(m.group(2))
    return "n/a", "n/a"

def _parse_network_from_connectivity_text(out: str) -> str:
    if not out: return "Disconnected"
    ok = ("state: CONNECTED" in out) and ("VALIDATED" in out)
    wifi = ("type: WIFI" in out)
    mobile = ("type: MOBILE" in out)
    if ok and wifi and not mobile: return "WiFi"
    if ok and mobile and not wifi: return "Mobile"
    if ok and wifi and mobile:     return "WiFi"
    return "Disconnected"

def obtener_red_real_via_appium(driver) -> str:
    try:
        res = driver.execute_script("mobile: shell", {
            "command": "dumpsys",
            "args": ["connectivity"],
            "includeStderr": True,
            "timeout": 7000
        })
        out = (res or {}).get("stdout", "") if isinstance(res, dict) else ""
        return _parse_network_from_connectivity_text(out)
    except Exception:
        return "Disconnected"

def obtener_red_real_via_adb(serial: str) -> str:
    res = adb(["shell", "dumpsys", "connectivity"], serial=serial, timeout=10)
    return _parse_network_from_connectivity_text(res.stdout or "")

def obtener_red_real_dual(driver, serial: str) -> str:
    # 1) Appium primero (más estable si el server ya está abierto)
    net = obtener_red_real_via_appium(driver)
    if net != "Disconnected":
        return net
    # 2) Respaldo ADB
    return obtener_red_real_via_adb(serial)

def device_now(serial: str) -> datetime:
    res = adb(["shell", "date", "+%s"], serial=serial, timeout=5)
    s = (res.stdout or "").strip()
    if s.isdigit(): return datetime.fromtimestamp(int(s))
    return datetime.now()

def _coords_str_now(serial: str) -> str:
    lat, lon = obtener_gps(serial)
    return f"{lat} {lon}"

def snapshot_net_gps(driver, serial: str):
    net = obtener_red_real_dual(driver, serial)
    lat, lon = obtener_gps(serial)
    return net, lat, lon

# ====== APPIUM ======
from appium import webdriver
from appium.webdriver.common.appiumby import AppiumBy
from appium.options.android import UiAutomator2Options

def build_driver(url: str, udid: str, system_port: int, new_command_timeout: int = 360):
    caps = {
        "platformName": "Android",
        "automationName": "UiAutomator2",
        "deviceName": udid,
        "udid": udid,
        "noReset": True,
        "systemPort": int(system_port),
        "newCommandTimeout": int(new_command_timeout),
        "disableWindowAnimation": True,
        "ignoreHiddenApiPolicyError": True,
    }
    options = UiAutomator2Options().load_capabilities(caps)
    return webdriver.Remote(command_executor=url, options=options)

def mobile_shell(driver, cmd: str, args=None, timeout_ms: int = 5000):
    if args is None: args = []
    try:
        return driver.execute_script("mobile: shell", {
            "command": cmd, "args": args, "timeout": timeout_ms, "includeStderr": True
        })
    except Exception as e:
        return {"stdout":"", "stderr": str(e)}

def wake_and_dismiss_keyguard(driver):
    try:
        mobile_shell(driver, "input", ["keyevent", "224"], timeout_ms=2500)
        mobile_shell(driver, "wm", ["dismiss-keyguard"],    timeout_ms=2500)
        mobile_shell(driver, "svc", ["power", "stayon", "usb"], timeout_ms=2500)
    except Exception:
        pass

_TIMER_TEXT_RE = re.compile(r"^(\d{1,2}:\d{2}|\d{1,2}:\d{2}:\d{2})$")
def ui_has_call_timer(driver) -> bool:
    try:
        ids = [
            "com.samsung.android.incallui:id/call_time",
            "com.samsung.android.incallui:id/chronometer",
            "com.android.incallui:id/chronometer",
            "com.google.android.dialer:id/contactgrid_bottom_timer",
            "com.google.android.dialer:id/incall_bottom_timer",
        ]
        for rid in ids:
            for e in driver.find_elements(AppiumBy.ID, rid):
                t = (e.text or "").strip()
                if _TIMER_TEXT_RE.match(t): return True
        for e in driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.Chronometer"):
            t = (e.text or "").strip()
            if _TIMER_TEXT_RE.match(t): return True
        for e in driver.find_elements(AppiumBy.XPATH, "//*[@text]"):
            t = (e.text or "").strip()
            if _TIMER_TEXT_RE.match(t): return True
    except Exception:
        pass
    return False

# ====== CONFIG TXT ======
def set_config_param(path_txt: str, key: str, value: str):
    try:
        with open(path_txt, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []
    idx_param_start = idx_param_end = None
    for i, raw in enumerate(lines):
        s = raw.strip()
        if s.startswith('#'):
            hdr = s.strip('#').strip().lower()
            if hdr.startswith('param'):
                idx_param_start = i
                j = i + 1
                while j < len(lines) and not lines[j].strip().startswith('#'):
                    j += 1
                idx_param_end = j
                break
    if idx_param_start is None:
        if lines and not lines[-1].endswith('\n'):
            lines[-1] += '\n'
        lines += ['\n# PARAM\n', f'{key}={value}\n']
    else:
        found = False
        for k in range(idx_param_start + 1, idx_param_end):
            if '=' in lines[k]:
                mk, _ = lines[k].split('=', 1)
                if mk.strip().lower() == key.lower():
                    lines[k] = f'{key}={value}\n'; found = True; break
        if not found:
            lines.insert(idx_param_end, f'{key}={value}\n')
    with open(path_txt, 'w', encoding='utf-8') as f:
        f.writelines(lines)

def leer_plan_config(path_txt: str):
    global ROLE_CONFIG, CONTACTO, CDR_HOLD_S, CALL_ID, ANSWER_TIMEOUT_S
    TIEMPO_ENTRE_CICLOS = 5.0
    seccion = None
    pruebas_norm = []
    last_act = None

    def normaliza_prueba(linea: str):
        s = linea.strip().lower().replace('+',' y ')
        s = ' '.join(s.split())
        if ('llamar' in s) or ('llamada' in s) or ('run' in s): return 'run_llamar'
        if 'cdr' in s: return 'cdr'
        if ('cst' in s) and ('csfr' in s): return 'cst_csfr'
        return None

    try:
        with open(path_txt, 'r', encoding='utf-8') as f:
            for raw in f:
                line = raw.strip()
                if not line: continue
                if line.startswith('#'):
                    h = line.strip('#').strip().upper()
                    if   h.startswith('PARAM'):      seccion = 'PARAM'
                    elif h.startswith('CONTACTO'):   seccion = 'CONTACTO'
                    elif h.startswith('PRUEBA'):     seccion = 'PRUEBA'
                    else: seccion = None
                    continue
                if seccion == 'PARAM' and '=' in line:
                    k, v = line.split('=', 1)
                    k = k.strip().lower(); v = v.strip()
                    if k == 'tiempo_entre_ciclos':
                        try: TIEMPO_ENTRE_CICLOS = float(v)
                        except: pass
                    elif k in ('cdr_hold_s','cdr_hold','hold'):
                        try: CDR_HOLD_S = int(float(v))
                        except: pass
                    elif k in ('call_id','callid','call_id_start'):
                        try: CALL_ID = int(float(v))
                        except: pass
                    elif k == 'role':
                        vv = v.lower()
                        if vv in ('a','b','both'):
                            ROLE_CONFIG = 'A' if vv=='a' else ('B' if vv=='b' else 'both')
                    elif k in ('answer_timeout_s','answer_timeout'):
                        try: ANSWER_TIMEOUT_S = float(v)
                        except: pass
                    continue
                if seccion == 'CONTACTO':
                    CONTACTO = line.strip(); continue
                if seccion == 'PRUEBA':
                    s = line.strip().lower()
                    if s.startswith('loop'):
                        rest = s[4:].strip().replace(':',' ').replace('=',' ')
                        rest = re.sub(r'\bx\b', ' ', rest)
                        parts = [p for p in rest.split() if p]
                        act = None; cnt = None
                        if parts:
                            if parts[0].isdigit():
                                cnt = int(parts[0]); act = last_act or 'run_llamar'
                            else:
                                act = normaliza_prueba(parts[0]) or last_act or 'run_llamar'
                                if len(parts) > 1 and parts[1].isdigit():
                                    cnt = int(parts[1])
                        if cnt is None: cnt = 1
                        for _ in range(max(0, cnt)): pruebas_norm.append(act)
                        last_act = act; continue
                    act = normaliza_prueba(s)
                    if act: pruebas_norm.append(act); last_act = act; continue
    except FileNotFoundError:
        pruebas_norm = ['run_llamar']
    if not pruebas_norm:
        pruebas_norm = ['run_llamar']
    return pruebas_norm, TIEMPO_ENTRE_CICLOS

# ====== CONEXIÓN (UI-first) ======
def wait_for_connect(serial: str, driver, timeout_s: float) -> bool:
    deadline = time.monotonic() + float(timeout_s)
    last_tel_check = 0.0
    while time.monotonic() < deadline:
        if should_stop(): return False
        try:
            if ui_has_call_timer(driver):
                return True
        except Exception:
            pass
        now = time.monotonic()
        if now - last_tel_check >= 2.5:
            last_tel_check = now
            if telecom_phase(serial) == "ACTIVE":
                return True
        time.sleep(0.2)
    return False

# ====== CORE DE LLAMADA ======
def run_llamar(driver_a, contacto, hold_s=None, drop_grace=None, call_id=0):
    serial = UDID_A_RUNTIME
    if not serial: raise RuntimeError("UDID_A_RUNTIME no está definido.")
    if hold_s is None: hold_s = float(CDR_HOLD_S)
    if drop_grace is None: drop_grace = float(DROP_GRACE_S)

    if should_stop(): return
    ensure_idle_before_dial(serial, max_wait_s=5.0)
    if should_stop(): return

    start_dt = device_now(serial)
    log_evt("CALL_START", start_dt, extra=f"to={contacto}")
    try: wake_and_dismiss_keyguard(driver_a)
    except Exception: pass

    try:
        dial_via_adb(serial, contacto)
        if not sleep_coop(float(CALL_START_SETTLE_S), 0.1):
            force_hangup_and_wait_idle(serial, grace_s=drop_grace, verify_timeout_s=3.0)
            return
    except Exception:
        end_dt = device_now(serial)
        net, lat, lon = snapshot_net_gps(driver_a, serial)
        extra_fail = _coords_str_now(serial)
        csv_write_device(csvw_device, "RUN_LLAMAR", call_id, contacto,
                         start_dt, end_dt, result="Failed", failure="Dial failed",
                         extra=extra_fail, lat=lat, lon=lon, network=net)
        log_evt("CALL_FAIL_START", end_dt)
        return

    if should_stop():
        force_hangup_and_wait_idle(serial, grace_s=drop_grace, verify_timeout_s=3.0)
        return

    connected = wait_for_connect(serial, driver_a, timeout_s=float(ANSWER_TIMEOUT_S))

    if should_stop():
        force_hangup_and_wait_idle(serial, grace_s=drop_grace, verify_timeout_s=3.0)
        return

    if not connected:
        force_hangup_and_wait_idle(serial, grace_s=NOANSWER_HANGUP_GRACE_S, verify_timeout_s=NOANSWER_VERIFY_TIMEOUT_S)
        end_dt = device_now(serial)
        net, lat, lon = snapshot_net_gps(driver_a, serial)
        extra_timeout = _coords_str_now(serial)
        csv_write_device(csvw_device, "RUN_LLAMAR", call_id, contacto,
                         start_dt, end_dt, result="Failed", failure=f"No answer within {int(ANSWER_TIMEOUT_S)}s",
                         extra=extra_timeout, lat=lat, lon=lon, network=net)
        log_evt("CALL_NO_ANSWER_TIMEOUT", end_dt)
        return

    t0 = time.monotonic()
    dropped = False
    extra_drop = ""
    while (time.monotonic() - t0) < float(hold_s):
        if should_stop(): break
        if is_call_idle(serial):
            dropped = True
            extra_drop = _coords_str_now(serial)
            break
        time.sleep(0.2)

    # hangup rápido para no alargar el total
    force_hangup_fast(serial)
    if not is_call_idle(serial):
        force_hangup_and_wait_idle(serial, grace_s=0.3, verify_timeout_s=1.5)

    end_dt = device_now(serial)
    net, lat, lon = snapshot_net_gps(driver_a, serial)
    if dropped:
        csv_write_device(csvw_device, "RUN_LLAMAR", call_id, contacto,
                         start_dt, end_dt, result="Failed", failure="Call dropped early",
                         extra=(extra_drop or _coords_str_now(serial)),
                         lat=lat, lon=lon, network=net)
        log_evt("CALL_DROP", end_dt)
    else:
        csv_write_device(csvw_device, "RUN_LLAMAR", call_id, contacto,
                         start_dt, end_dt, result="Successful", failure="",
                         extra=f"hold_s = {int(hold_s)}s", lat=lat, lon=lon, network=net)
        log_evt("CALL_END_OK", end_dt)

# ====== MAIN ======
def main():
    global CONTACTO, CDR_HOLD_S, UDID_A_RUNTIME
    global UDID_A, APPIUM_URL_A, SYSTEM_PORT_A
    global ANSWER_TIMEOUT_S, CALL_ID

    args = parse_args()
    plan_path = args.plan or PLAN_TXT
    pruebas, tiempo_entre_ciclos = leer_plan_config(plan_path)

    if args.udid_a:           UDID_A = args.udid_a
    if args.contacto:         CONTACTO = args.contacto
    if args.hold is not None: CDR_HOLD_S = int(args.hold)
    if args.appium_url_a:     APPIUM_URL_A = args.appium_url_a
    if args.system_port_a:    SYSTEM_PORT_A = int(args.system_port_a)
    if args.answer_timeout_s is not None:
        ANSWER_TIMEOUT_S = float(args.answer_timeout_s)
    if args.tiempo_entre_ciclos is not None:
        tiempo_entre_ciclos = float(args.tiempo_entre_ciclos)

    UDID_A_RUNTIME = UDID_A

    csv_init_all()
    csv_init_device()

    driver_a = None
    try:
        driver_a = build_driver(APPIUM_URL_A, UDID_A_RUNTIME, SYSTEM_PORT_A)
        wake_and_dismiss_keyguard(driver_a)

        for i, accion in enumerate(pruebas, 1):
            if should_stop(): break
            print(f"[RUN] {accion.upper()} -> '{CONTACTO}'")
            if accion == 'run_llamar':
                run_llamar(driver_a, CONTACTO, hold_s=CDR_HOLD_S, drop_grace=DROP_GRACE_S, call_id=CALL_ID)
                CALL_ID += 1
            elif accion == 'cst_csfr':
                print("Se encuentra comentado")
            elif accion == 'cdr':
                print("Se encuentra comentado")

            print(f"[RUN] Fin {accion.upper()}")
            if not sleep_coop(float(INTERCALL_EXTRA_GAP_S), 0.2): break
            if i < len(pruebas) and not should_stop():
                print(f"[RUN] Esperando {tiempo_entre_ciclos}s...")
                if not sleep_coop(float(tiempo_entre_ciclos), 0.2): break
    finally:
        try:
            if UDID_A_RUNTIME:
                force_hangup_and_wait_idle(UDID_A_RUNTIME, grace_s=1.0, verify_timeout_s=3.0)
        except: pass
        sleep_coop(0.3, 0.1)
        try:
            if driver_a: driver_a.quit()
        except: pass
        for w in (csvw_all, csvw_device):
            try:
                if w: w.close()
            except: pass

if __name__ == "__main__":
    iniciar_logs(
        udid=UDID_A,
        server_url=APPIUM_URL_A,
        start_data_sequence=False,
        background_after=True,
        caps_overrides={"systemPort": 8240, "mjpegServerPort": 7815}
    )
    main()
