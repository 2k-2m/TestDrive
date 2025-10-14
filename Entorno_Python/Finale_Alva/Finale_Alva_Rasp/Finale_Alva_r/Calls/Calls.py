# Calls.py
import os, csv, time, re, signal, argparse, subprocess, unicodedata
from datetime import datetime

from appium import webdriver
from appium.webdriver.common.appiumby import AppiumBy
from appium.options.android import UiAutomator2Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ====== RUTAS / PLAN ======
BASE_DIR = os.path.dirname(__file__)
PLAN_TXT = os.path.join(BASE_DIR, "configuracion.txt")
STOP_FILE = os.path.join(BASE_DIR, "stop.flag")

# ====== CONFIG PREDETERMINADA ======
UDID_A         = "RF8MB0G4KTJ"
APPIUM_URL_A   = "http://127.0.0.1:4793"
SYSTEM_PORT_A  = 8220

CONTACTO             = "567"
TIEMPO_ENTRE_CICLOS  = 2.0
ROLE_CONFIG          = "both"

# ====== TIMEOUTS / PARAMS ======
CDR_HOLD_S           = 10
DROP_GRACE_S         = 2.0
ANSWER_TIMEOUT_S     = 30.0   # tiempo máx. para detectar conexión (UI o telecom)
CALL_START_SETTLE_S  = 0.8    # gracia tras marcar (UI/stack)
INTERCALL_EXTRA_GAP_S = 1.5   # gap extra entre llamadas

# ====== CSV ======
timestamp_pc = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

CSV_HEADER = [
    "App","Network","Evento","CallID","Contact",
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

csvw_all    = None
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

def csv_write_device(csvw, driver, evento, call_id, contact,
                     start_dt, end_dt, result, failure="",
                     extra="", app="Phone", checkpoint=False,
                     device_label=None, udid=None):
    if device_label is None or udid is None:
        device_label = "A"; udid = UDID_A_RUNTIME
    network = obtener_red_real(driver) or ""
    lat, lon = ("n/a","n/a") if not udid else obtener_gps(udid)
    csvw.row([
        app, network, evento, call_id, contact,
        lat, lon,
        start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        result, failure, extra
    ], checkpoint=checkpoint)
    if csvw_all is not None and device_label and udid:
        csvw_all.row([
            app, device_label, udid, network, evento, call_id, contact,
            lat, lon,
            start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            result, failure, extra
        ], checkpoint=checkpoint)

# ====== CLI ======
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

# ====== SEÑALES / STOP ======
detener = False
def manejar_senal(sig, frame):
    global detener
    print("\n[INFO] Señal de terminación recibida. El script se detendrá con gracia...")
    detener = True
signal.signal(signal.SIGINT, manejar_senal)
signal.signal(signal.SIGTERM, manejar_senal)

def should_stop():
    return detener or os.path.exists(STOP_FILE)

def sleep_coop(total_s: float, step_s: float = 0.2) -> bool:
    """Espera cooperativa: se puede cortar por should_stop(). Devuelve False si se pidió parar."""
    t = 0.0
    while t < float(total_s):
        if should_stop(): return False
        time.sleep(step_s)
        t += step_s
    return True

# ====== APPIUM DRIVER ======
def build_driver(url, udid, system_port, force_launch=True):
    caps = {
        "platformName": "Android",
        "automationName": "UiAutomator2",
        "deviceName": udid,
        "udid": udid,
        "noReset": True,
        "systemPort": system_port,
        "newCommandTimeout": 360,
        "disableWindowAnimation": True,
        "ignoreHiddenApiPolicyError": True,
    }
    options = UiAutomator2Options().load_capabilities(caps)
    return webdriver.Remote(command_executor=url, options=options)

def esperar(drv, cond, t=10):
    return WebDriverWait(drv, t).until(cond)

def mobile_shell(d, cmd, args, timeout=3000):
    return d.execute_script("mobile: shell", {
        "command": cmd,
        "args": args,
        "timeout": timeout,
        "includeStderr": True
    })

def wake_and_dismiss_keyguard(driver):
    try:
        mobile_shell(driver, "input", ["keyevent", "224"])      # encender pantalla
        mobile_shell(driver, "wm", ["dismiss-keyguard"])        # quitar lockscreen
        mobile_shell(driver, "svc", ["power", "stayon", "usb"]) # pantalla siempre encendida por USB
    except Exception:
        pass

def preflight_device(driver):
    wake_and_dismiss_keyguard(driver)

# ====== ANDROID / RED / GPS ======
def obtener_red_real(driver):
    try:
        out = driver.execute_script("mobile: shell", {
            "command": "dumpsys",
            "args": ["connectivity"],
            "includeStderr": True,
            "timeout": 7000
        })["stdout"]
        if "state: CONNECTED" in out and "VALIDATED" in out:
            if "type: WIFI" in out:   return "WiFi"
            if "type: MOBILE" in out: return "Mobile"
    except:
        pass
    return "Disconnected"

def obtener_gps(udid):
    try:
        output = subprocess.check_output(
            ["adb", "-s", udid, "shell", "dumpsys", "location"],
            encoding="utf-8"
        )
        match = re.search(r'gps:\s+Location\[gps\s+([-\d\.]+),\s*([-\d\.]+)', output, re.I)
        if match:
            return str(match.group(1)), str(match.group(2))
    except Exception as e:
        print(f"Error obteniendo GPS vía ADB: {e}")
    return "n/a", "n/a"

def device_now(driver):
    out = driver.execute_script("mobile: shell", {
        "command":"date","args":["+%s"],"includeStderr":True,"timeout":3000
    })
    epoch_s = str(out.get("stdout","")).strip()
    if not epoch_s.isdigit():
        raise RuntimeError(f"date +%s inválido: {epoch_s!r}")
    return datetime.fromtimestamp(int(epoch_s))

# ====== NORMALIZACIÓN ======
def _norm(s: str) -> str:
    s = (s or "").lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )

# ====== ADB CORE ======
def adb(cmd_list, serial=None, timeout=15):
    base = ["adb"]
    if serial:
        base += ["-s", serial]
    return subprocess.run(base + cmd_list, text=True, capture_output=True, timeout=timeout, check=True)

# ====== ESTADOS DE TELEFONÍA ======
_TEL_STATE_RE = re.compile(r"\bmCallState\s*=\s*(\d+)\b")
def _telephony_call_state(serial: str) -> int:
    """
    0 = IDLE, 1 = RINGING (entrante), 2 = OFFHOOK (DIALING/ALERTING/ACTIVE)
    """
    out = adb(["shell", "dumpsys", "telephony.registry"], serial=serial, timeout=8).stdout
    m = _TEL_STATE_RE.search(out)
    if not m: return -1
    try: return int(m.group(1))
    except: return -1

def is_call_ringing(serial: str) -> bool: return _telephony_call_state(serial) == 1
def is_call_active(serial: str) -> bool:  return _telephony_call_state(serial) == 2
def is_call_idle(serial: str) -> bool:    return _telephony_call_state(serial) == 0

# ====== TELECOM (alto-nivel) ======
_PHASE_RE = re.compile(r"\bSTATE\s*:\s*(DIALING|ALERTING|RINGING|ACTIVE)\b", re.I)
def telecom_phase(serial: str) -> str:
    try:
        out = adb(["shell","dumpsys","telecom"], serial=serial, timeout=8).stdout
    except Exception:
        return "UNKNOWN"
    phases = _PHASE_RE.findall(out)
    return (phases[-1].upper() if phases else "UNKNOWN")

def is_connected(serial: str) -> bool:
    return telecom_phase(serial) == "ACTIVE"

# ====== MARCAR / COLGAR ======
def dial_via_adb(serial: str, number: str, pause_before_press=0.5):
    adb(["shell","am","start","-a","android.intent.action.DIAL","-d", f"tel:{number}"], serial=serial)
    time.sleep(max(0.1, float(pause_before_press)))
    adb(["shell","input","keyevent","5"], serial=serial)

def hangup(serial: str):
    try:
        adb(["shell","cmd","telecom","end-call"], serial=serial, timeout=5)
    except Exception:
        try:
            adb(["shell","input","keyevent","6"], serial=serial, timeout=5)
        except Exception:
            pass

# ====== COLGAR SEGURO ======
def force_hangup_and_wait_idle(serial: str, grace_s: float = 2.0, verify_timeout_s: float = 8.0):
    """Cuelga y se asegura de que el estado vuelva a IDLE antes de salir."""
    try:
        try:
            adb(["shell","cmd","telecom","end-call"], serial=serial, timeout=5)
        except Exception:
            adb(["shell","input","keyevent","6"], serial=serial, timeout=5)
    except Exception:
        pass

    sleep_coop(grace_s, 0.2)

    if not wait_until(lambda: is_call_idle(serial), timeout_s=verify_timeout_s, interval_s=0.3):
        try: adb(["shell","input","keyevent","6"], serial=serial, timeout=5)
        except Exception: pass
        sleep_coop(1.0, 0.2)
        _ = wait_until(lambda: is_call_idle(serial), timeout_s=verify_timeout_s, interval_s=0.3)

def ensure_idle_before_dial(serial: str, max_wait_s: float = 5.0):
    """Asegura que el equipo esté en IDLE antes de intentar marcar."""
    if not wait_until(lambda: is_call_idle(serial), timeout_s=max_wait_s, interval_s=0.25):
        # Forzar colgado si fuese necesario
        force_hangup_and_wait_idle(serial, grace_s=1.0, verify_timeout_s=5.0)

# ====== UTILS ======
def wait_until(fn, timeout_s=10.0, interval_s=0.25, cancel_fn=should_stop):
    t0 = time.monotonic()
    while (time.monotonic() - t0) < timeout_s:
        if cancel_fn and cancel_fn():
            return False
        try:
            if fn():
                return True
        except Exception:
            pass
        time.sleep(interval_s)
    return False

# ====== Appium: detectar timer de llamada conectada ======
_TIMER_TEXT_RE = re.compile(r"^(\d{1,2}:\d{2}|\d{1,2}:\d{2}:\d{2})$")

def ui_has_call_timer(driver) -> bool:
    try:
        candidate_ids = [
            "com.samsung.android.incallui:id/call_time",
            "com.samsung.android.incallui:id/chronometer",
            "com.android.incallui:id/chronometer",
            "com.google.android.dialer:id/contactgrid_bottom_timer",
            "com.google.android.dialer:id/incall_bottom_timer",
        ]
        for rid in candidate_ids:
            els = driver.find_elements(AppiumBy.ID, rid)
            for e in els:
                t = (e.text or "").strip()
                if _TIMER_TEXT_RE.match(t):
                    return True

        chrono = driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.Chronometer")
        for e in chrono:
            t = (e.text or "").strip()
            if _TIMER_TEXT_RE.match(t):
                return True

        els = driver.find_elements(AppiumBy.XPATH, "//*[@text]")
        for e in els:
            t = (e.text or "").strip()
            if _TIMER_TEXT_RE.match(t):
                return True
    except Exception:
        pass
    return False

# ====== LOG ======
DEBUG = True
CALL_ID = 0
def log_evt(k: str, when: datetime | None = None, extra: str = ""):
    if not DEBUG: return
    if when is None: when = datetime.now()
    ts = when.strftime("%H:%M:%S")
    print(f"[DBG] [EVT] {k} @ {ts}{(' | '+extra) if extra else ''}")

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
        lines += ['\n# PARAMETRO\n', f'{key}={value}\n']
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

# ====== PLAN / CONFIGURACION.TXT ======
def leer_plan_config(path_txt: str):
    global TIEMPO_ENTRE_CICLOS, CONTACTO, CDR_HOLD_S, CALL_ID, ROLE_CONFIG, ANSWER_TIMEOUT_S
    seccion = None
    pruebas_norm = []
    last_act = None

    def normaliza_prueba(linea: str):
        s = linea.strip().lower()
        s = s.replace('+', ' y ')
        s = ' '.join(s.split())
        if ('llamar' in s) or ('llamada' in s) or ('run' in s):
            return 'run_llamar'
        if 'cdr' in s: return 'cdr'
        if ('cst' in s) and ('csfr' in s): return 'cst_csfr'
        return None

    try:
        with open(path_txt, 'r', encoding='utf-8') as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                if line.startswith('#'):
                    h = line.strip('#').strip().upper()
                    if h.startswith('PARAM'):      seccion = 'PARAM'
                    elif h.startswith('CONTACTO'): seccion = 'CONTACTO'
                    elif h.startswith('PRUEBA'):   seccion = 'PRUEBA'
                    else: seccion = None
                    continue

                if seccion == 'PARAM':
                    if '=' in line:
                        k, v = line.split('=', 1)
                        k = k.strip().lower(); v = v.strip()
                        if k == 'tiempo_entre_ciclos':
                            try: TIEMPO_ENTRE_CICLOS = float(v)
                            except: TIEMPO_ENTRE_CICLOS = 0
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
                    if line: CONTACTO = line.strip()
                    continue

                if seccion == 'PRUEBA':
                    s = line.strip().lower()
                    if s.startswith('loop'):
                        rest = s[4:].strip()
                        rest = rest.replace(':', ' ').replace('=', ' ')
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
                        for _ in range(max(0, cnt)):
                            pruebas_norm.append(act)
                        last_act = act
                        continue

                    act = normaliza_prueba(s)
                    if act:
                        pruebas_norm.append(act)
                        last_act = act
                    continue
    except FileNotFoundError:
        pruebas_norm = ['run_llamar']

    return pruebas_norm

# ====== CORE DE LLAMADA ======
def run_llamar(driver_a, _driver_b_no_usado, contacto, hold_s=10, drop_grace=2.0, auto_answer_b=False):
    global ANSWER_TIMEOUT_S
    serial = UDID_A_RUNTIME
    if not serial:
        raise RuntimeError("UDID_A_RUNTIME no está definido.")

    # Si pidieron parar, respeta aquí
    if should_stop():
        return

    # Asegura IDLE real antes de marcar
    ensure_idle_before_dial(serial, max_wait_s=5.0)
    if should_stop():
        return

    start_dt = device_now(driver_a)
    log_evt("CALL_START", start_dt, extra=f"to={contacto}")

    # Pantalla encendida
    wake_and_dismiss_keyguard(driver_a)

    # --- Marcar por ADB (DIAL + KEYCODE_CALL) ---
    try:
        dial_via_adb(serial, contacto)
        if not sleep_coop(CALL_START_SETTLE_S, 0.1):
            # si paran aquí, cuelga y termina
            force_hangup_and_wait_idle(serial, grace_s=float(drop_grace), verify_timeout_s=5.0)
            return
    except Exception as e:
        end_dt = device_now(driver_a)
        csv_write_device(csvw_device, driver_a, "RUN_LLAMAR", CALL_ID, contacto,
                         start_dt, end_dt, result="FAIL", failure=str(e), extra="dial_via_adb/start")
        log_evt("CALL_FAIL_START", end_dt, extra=str(e))
        return

    if should_stop():
        force_hangup_and_wait_idle(serial, grace_s=float(drop_grace), verify_timeout_s=5.0)
        return

    # --- Detectar conexión por UI (timer) o por telecom ACTIVE ---
    saw_timer = False
    last_phase = "UNKNOWN"

    def _connected_or_update_flags():
        nonlocal saw_timer, last_phase
        if should_stop():
            return False
        try:
            if ui_has_call_timer(driver_a):
                saw_timer = True
                return True
        except Exception:
            pass
        p = telecom_phase(serial)
        if p != "UNKNOWN":
            last_phase = p
        return (p == "ACTIVE")

    connected = wait_until(_connected_or_update_flags,
                           timeout_s=float(ANSWER_TIMEOUT_S),
                           interval_s=0.5,
                           cancel_fn=should_stop)

    if should_stop():
        force_hangup_and_wait_idle(serial, grace_s=float(drop_grace), verify_timeout_s=5.0)
        return

    if not connected:
        # No hubo conexión “real”: cortar y registrar con contexto
        force_hangup_and_wait_idle(serial, grace_s=float(drop_grace), verify_timeout_s=8.0)
        end_dt = device_now(driver_a)
        csv_write_device(csvw_device, driver_a, "RUN_LLAMAR", CALL_ID, contacto,
                         start_dt, end_dt, result="NO_ANSWER_TIMEOUT",
                         failure="No CONNECT (UI/telecom) before timeout",
                         extra=f"last_phase={last_phase}, saw_timer={saw_timer}")
        log_evt("CALL_NO_ANSWER_TIMEOUT", end_dt, extra=f"last_phase={last_phase} saw_timer={saw_timer}")
        return

    # --- Sostener la llamada y vigilar DROP ---
    t0 = time.monotonic()
    dropped = False
    while (time.monotonic() - t0) < float(hold_s):
        if should_stop():
            # solicitaron parar: colgamos y salimos
            dropped = False
            break
        if is_call_idle(serial):  # se colgó / cayó antes de tiempo
            dropped = True
            break
        time.sleep(0.2)

    # Colgar al final del hold (o si pidieron parar) y garantizar IDLE
    force_hangup_and_wait_idle(serial, grace_s=float(drop_grace), verify_timeout_s=8.0)

    end_dt = device_now(driver_a)
    if dropped:
        csv_write_device(csvw_device, driver_a, "RUN_LLAMAR", CALL_ID, contacto,
                         start_dt, end_dt, result="DROP", failure="EARLY_DISCONNECT",
                         extra=f"hold_target={hold_s}s")
        log_evt("CALL_DROP", end_dt)
    else:
        csv_write_device(csvw_device, driver_a, "RUN_LLAMAR", CALL_ID, contacto,
                         start_dt, end_dt, result="OK", failure="",
                         extra=f"hold_s={hold_s}")
        log_evt("CALL_END_OK", end_dt)

# ====== MAIN ======
def main():
    global CONTACTO, CDR_HOLD_S, UDID_A_RUNTIME
    global UDID_A, APPIUM_URL_A, SYSTEM_PORT_A
    global TIEMPO_ENTRE_CICLOS, ANSWER_TIMEOUT_S

    args = parse_args()

    plan_path = args.plan or PLAN_TXT
    pruebas = leer_plan_config(plan_path)

    if args.udid_a:            UDID_A = args.udid_a
    if args.contacto:          CONTACTO = args.contacto
    if args.hold is not None:  CDR_HOLD_S = int(args.hold)
    if args.tiempo_entre_ciclos is not None:
        TIEMPO_ENTRE_CICLOS = float(args.tiempo_entre_ciclos)
    if args.appium_url_a:      APPIUM_URL_A = args.appium_url_a
    if args.system_port_a:     SYSTEM_PORT_A = int(args.system_port_a)
    if args.answer_timeout_s is not None:
        ANSWER_TIMEOUT_S = float(args.answer_timeout_s)

    UDID_A_RUNTIME = UDID_A

    csv_init_all()
    csv_init_device()

    driver_a = None
    try:
        driver_a = build_driver(APPIUM_URL_A, UDID_A_RUNTIME, SYSTEM_PORT_A, force_launch=True)
        preflight_device(driver_a)

        for i, accion in enumerate(pruebas, 1):
            if should_stop(): break
            print(f"[RUN] Comenzando {accion.upper()} para '{CONTACTO}'...")

            if accion == 'run_llamar':
                # Asegura IDLE antes de cada intento
                ensure_idle_before_dial(UDID_A_RUNTIME, max_wait_s=5.0)
                if should_stop(): break

                run_llamar(driver_a, None, CONTACTO,
                           hold_s=CDR_HOLD_S, drop_grace=DROP_GRACE_S,
                           auto_answer_b=False)

            elif accion == 'cst_csfr':
                print("Se encuentra comentado")
            elif accion == 'cdr':
                print("Se encuentra comentado")

            print(f"[RUN] Terminada {accion.upper()}")

            # Gap extra
            if not sleep_coop(INTERCALL_EXTRA_GAP_S, 0.2): break

            # Espera configurada entre ciclos
            if i < len(pruebas) and not should_stop():
                print(f"[RUN] Esperando {TIEMPO_ENTRE_CICLOS}s...")
                if not sleep_coop(float(TIEMPO_ENTRE_CICLOS), 0.2):
                    break

    finally:
        try:
            if UDID_A_RUNTIME: force_hangup_and_wait_idle(UDID_A_RUNTIME, grace_s=1.5, verify_timeout_s=6.0)
        except: pass
        sleep_coop(0.5, 0.1)
        try:
            if driver_a: driver_a.quit()
        except: pass
        for w in (csvw_all, csvw_device):
            try:
                if w: w.close()
            except: pass

if __name__ == "__main__":
    main()

