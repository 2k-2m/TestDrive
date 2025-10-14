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
UDID_A = "6NUDU18529000033"
APPIUM_URL_A = "http://127.0.0.1:4723"
SYSTEM_PORT_A = 8208

UDID_B = "6NU7N18614004267"
APPIUM_URL_B = "http://127.0.0.1:4726"
SYSTEM_PORT_B = 8216

APP_PKG = "com.whatsapp"
APP_ACT = "com.whatsapp.HomeActivity"

CONTACTO = "0"
TIEMPO_ENTRE_CICLOS = 0
ROLE_CONFIG = "both"

# ====== TIMEOUTS / PARAMS ======
CST_TIMEOUT_S  = 20.0
CSFR_TIMEOUT_S = 20.0
CDR_HOLD_S     = 15
DROP_GRACE_S   = 2.0
WAIT_INCOMING_B_S = 25

PLAN_PATH_RUNTIME = PLAN_TXT

# ====== UBICACIÓN ======
def obtener_gps_desde_archivo(udid, ruta_archivo="/sdcard/DCIM/gps_last.txt"):
    try:
        output = subprocess.check_output(
            ["adb", "-s", udid, "shell", "cat", ruta_archivo],
            encoding='utf-8'
        ).strip()
        lat, lon = output.split(",")
        return lat.strip(), lon.strip()
    except Exception:
        return "n/a", "n/a"

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
        self.f = open(path, "a", newline="", encoding="utf-8")
        self.w = csv.writer(self.f)
        if os.path.getsize(path) == 0:
            self.w.writerow(header)
    def row(self, cells, checkpoint=False):
        self.w.writerow(cells)
        self.f.flush()
        if checkpoint:
            try: os.fsync(self.f.fileno())
            except: pass
    def close(self):
        try: self.f.close()
        except: pass

csvw_a = None
csvw_b = None
csvw_all = None

UDID_A_RUNTIME = None
UDID_B_RUNTIME = None

def csv_init(udid_a: str, udid_b: str, role: str = "both"):
    global csvw_a, csvw_b, csvw_all
    fn_all = os.path.join(BASE_DIR, f"Llamada_Whatsapp_{timestamp_pc}.csv")
    csvw_all = CsvWriter(fn_all, CSV_HEADER_ALL)
    if role in ("both", "A"):
        fn_a  = os.path.join(BASE_DIR, f"Llamada_Whatsapp_A_{timestamp_pc}.csv")
        csvw_a = CsvWriter(fn_a, CSV_HEADER)
    else:
        csvw_a = None
    if role in ("both", "B"):
        fn_b  = os.path.join(BASE_DIR, f"Llamada_Whatsapp_B_{timestamp_pc}.csv")
        csvw_b = CsvWriter(fn_b, CSV_HEADER)
    else:
        csvw_b = None

def csv_write_device(csvw, driver, evento, call_id, contact,
                     start_dt, end_dt, result, failure="",
                     extra="", app="WhatsApp", checkpoint=False,
                     device_label=None, udid=None):
    if device_label is None or udid is None:
        if csvw is csvw_a:
            device_label = "A"; udid = UDID_A_RUNTIME
        elif csvw is csvw_b:
            device_label = "B"; udid = UDID_B_RUNTIME
    network = obtener_red_real(driver) or ""
    lat, lon = ("n/a", "n/a") if not udid else obtener_gps_desde_archivo(udid)
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
    ap.add_argument("--udid-a", default=None)
    ap.add_argument("--udid-b", default=None)
    ap.add_argument("--contacto", default=None)
    ap.add_argument("--hold", type=int, default=None)
    ap.add_argument("--tiempo-entre-ciclos", type=float, default=None)
    ap.add_argument("--role", choices=["both", "A", "B"], default=None)
    ap.add_argument("--appium-url-a", default=None)
    ap.add_argument("--appium-url-b", default=None)
    ap.add_argument("--system-port-a", type=int, default=None)
    ap.add_argument("--system-port-b", type=int, default=None)
    return ap.parse_args()

# ====== SEÑALES / STOP ======
detener = False
def manejar_senal(sig, frame):
    global detener
    detener = True
signal.signal(signal.SIGINT, manejar_senal)
signal.signal(signal.SIGTERM, manejar_senal)
def should_stop():
    return detener or os.path.exists(STOP_FILE)

# ====== DRIVERS ======
def build_driver(url, udid, system_port, force_launch=True):
    caps = {
        "platformName": "Android",
        "automationName": "UiAutomator2",
        "deviceName": udid,
        "udid": udid,
        "appPackage": APP_PKG,
        "appActivity": APP_ACT,
        "noReset": True,
        "forceAppLaunch": bool(force_launch),
        "systemPort": system_port,
        "newCommandTimeout": 360,
        "disableWindowAnimation": True,
        "ignoreHiddenApiPolicyError": True,
    }
    options = UiAutomator2Options().load_capabilities(caps)
    return webdriver.Remote(command_executor=url, options=options)

# ====== ANDROID UTILS ======
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

def esperar(drv, cond, t=10):
    return WebDriverWait(drv, t).until(cond)

def device_now(driver):
    out = driver.execute_script("mobile: shell", {
        "command":"date","args":["+%s"],"includeStderr":True,"timeout":3000
    })
    epoch_s = str(out.get("stdout","")).strip()
    if not epoch_s.isdigit():
        raise RuntimeError(f"date +%s inválido: {epoch_s!r}")
    return datetime.fromtimestamp(int(epoch_s))

def wake_and_dismiss_keyguard(driver):
    try:
        driver.execute_script("mobile: shell", {"command":"input","args":["keyevent","224"]})
        driver.execute_script("mobile: shell", {"command":"wm","args":["dismiss-keyguard"]})
    except:
        pass

def preflight_device(drv, pkg):
    wake_and_dismiss_keyguard(drv)
    try:
        drv.activate_app(pkg)
    except:
        pass

# ====== SELECTORES ======
ROW_IDS = ["com.whatsapp:id/contact_row_container"]
ROW_HEADER_ID = "com.whatsapp:id/conversations_row_contact_name"
SEARCH_BAR_ID = "com.whatsapp:id/my_search_bar"

VOICE_CALL_ACCS = ("Llamada",)

CALL_HEADER_ID        = "com.whatsapp:id/call_screen_header_view"
CALL_SUBTITLE_ID      = "com.whatsapp:id/subtitle"
CALL_CONTROLS_CARD_ID = "com.whatsapp:id/call_controls_card"
END_CALL_BTN_ID       = "com.whatsapp:id/end_call_button"

B_CALL_ROOT_ID         = "com.whatsapp:id/call_screen_root"
B_ANSWER_ROOT_ID       = "com.whatsapp:id/answer_call_view_id"
B_ACCEPT_CONTAINER_ID  = "com.whatsapp:id/accept_incoming_call_container"
B_ACCEPT_SWIPE_HINT_ID = "com.whatsapp:id/accept_call_swipe_up_hint_view"
B_ACCEPT_BUTTON_ID     = "com.whatsapp:id/accept_incoming_call_view"

_CONNECTED_RE      = re.compile(r"^\d{1,2}:\d{2}$")
SUBTITLE_POSITIVES = ("cifrado", "llamando", "calling", "sonando", "ringing")
RECON_TOKENS = ("reconect", "reconnect", "reconnec")

# ====== NAVEGACIÓN ======
CHAT_TITLE_IDS = [
    "com.whatsapp:id/conversation_contact_name",
    "com.whatsapp:id/toolbar_title",
]

def is_in_chats_list(driver) -> bool:
    try:
        if driver.find_elements(AppiumBy.ID, ROW_IDS[0]):
            return True
    except:
        pass
    try:
        driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().description("Chats")')
        return True
    except:
        return False

def is_in_chat_with(driver, contacto: str) -> bool:
    try:
        has_entry = bool(driver.find_elements(AppiumBy.ID, "com.whatsapp:id/entry"))
        if not has_entry:
            return False
    except:
        return False
    for tid in CHAT_TITLE_IDS:
        try:
            t = (driver.find_element(AppiumBy.ID, tid).text or "").strip()
            if t and contacto.lower() in t.lower():
                return True
        except:
            continue
    return False

def go_to_chats_tab(driver):
    try:
        driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR,'new UiSelector().description("Chats")').click()
        time.sleep(0.5)
    except:
        pass

def open_chat(driver, contacto: str) -> bool:
    try:
        filas = driver.find_elements(AppiumBy.ID, ROW_IDS[0])
        for fila in filas:
            try:
                header = fila.find_element(AppiumBy.ID, ROW_HEADER_ID)
                nombre = (header.text or "").strip()
                if contacto.lower() in (nombre or "").lower():
                    fila.click()
                    esperar(driver, EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/entry")), 8)
                    return True
            except:
                continue
    except:
        pass
    try:
        driver.find_element(AppiumBy.ID, SEARCH_BAR_ID).click()
        box = driver.switch_to.active_element
        box.clear(); box.send_keys(contacto)
        time.sleep(1.0)
        res = driver.find_elements(AppiumBy.ID, ROW_IDS[0])
        if res:
            res[0].click()
            esperar(driver, EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/entry")), 8)
            return True
    except:
        pass
    return False

def ensure_chat_open(driver, contacto: str, retries=2) -> bool:
    for _ in range(retries + 1):
        if is_in_chat_with(driver, contacto):
            return True
        try: driver.activate_app(APP_PKG)
        except: pass
        if is_in_chats_list(driver) and open_chat(driver, contacto):
            return True
        go_to_chats_tab(driver)
        if open_chat(driver, contacto):
            return True
    return False

# ====== TEXTO / ESTADOS AUX ======
NO_ANSWER_TOKENS = (
    "sin respuesta", "no contesto", "no contestó", "no respondio",
    "didn't answer", "didnt answer", "no answer"
)

def _norm(s: str) -> str:
    s = (s or "").lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )

def is_no_answer_text(txt: str) -> bool:
    t = _norm(txt)
    return any(tok in t for tok in NO_ANSWER_TOKENS)

def has_no_answer_cta(driver) -> bool:
    try:
        return bool(driver.find_elements(AppiumBy.ID, "com.whatsapp:id/cancel_call_back_text"))
    except:
        return False

# ====== LLAMADA ======
def stable_text(el, ms=250):
    t0 = time.monotonic()
    last = el.text or ""
    while (time.monotonic()-t0)*1000 < ms:
        cur = el.text or ""
        if cur != last:
            t0 = time.monotonic()
            last = cur
        time.sleep(0.03)
    return (last or "").strip().lower().replace("…", "...")

def find_subtitle_text(driver) -> str:
    try:
        header = driver.find_element(AppiumBy.ID, CALL_HEADER_ID)
        sub = header.find_element(AppiumBy.ID, CALL_SUBTITLE_ID)
        return stable_text(sub)
    except:
        pass
    try:
        sub = driver.find_element(AppiumBy.ID, CALL_SUBTITLE_ID)
        return stable_text(sub)
    except:
        return ""

def tocar_boton_llamar(driver):
    for acc in VOICE_CALL_ACCS:
        try:
            WebDriverWait(driver, 6).until(
                EC.element_to_be_clickable((AppiumBy.ACCESSIBILITY_ID, acc))
            ).click()
            try:
                WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((AppiumBy.ID, "android:id/button1"))
                ).click()
            except:
                pass
            return
        except:
            pass
    el = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((
        AppiumBy.XPATH, "//*[contains(@content-desc,'Llam')] | //*[@content-desc[contains(.,'Call')]]"
    )))
    el.click()

def colgar_seguro(driver, wait_s=5):
    try:
        card = WebDriverWait(driver, wait_s).until(
            EC.presence_of_element_located((AppiumBy.ID, CALL_CONTROLS_CARD_ID))
        )
        card.find_element(AppiumBy.ID, END_CALL_BTN_ID).click()
        return
    except:
        pass
    try:
        WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((AppiumBy.ID, END_CALL_BTN_ID))
        ).click()
        return
    except:
        pass
    try:
        driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Abandonar la llamada").click()
    except:
        pass

# ====== AUTO-ANSWER EN B ======
def _center(rect):
    return (rect["x"] + rect["width"] // 2, rect["y"] + rect["height"] // 2)

def _w3c_swipe_up(driver_b, start_x, start_y, end_y, hold_ms=320, move_ms=800):
    actions = [{
        "type": "pointer",
        "id": "finger1",
        "parameters": {"pointerType": "touch"},
        "actions": [
            {"type": "pointerMove", "duration": 0, "x": int(start_x), "y": int(start_y)},
            {"type": "pointerDown", "button": 0},
            {"type": "pause", "duration": int(hold_ms)},
            {"type": "pointerMove", "duration": int(move_ms), "x": int(start_x), "y": int(end_y)},
            {"type": "pointerUp", "button": 0},
        ],
    }]
    driver_b.perform_actions(actions)
    try:
        driver_b.release_actions()
    except:
        pass

def _drag_up_via_gesture(driver_b, el, pct=0.75, duration=850):
    r = el.rect
    cx, cy = _center(r)
    end_y = max(0, int(cy - r["height"] * pct))
    driver_b.execute_script("mobile: dragGesture", {
        "elementId": el.id,
        "endX": int(cx),
        "endY": int(end_y),
        "duration": int(duration)
    })

def wait_incoming_on_b(driver_b, wait_s=WAIT_INCOMING_B_S):
    t_end = time.monotonic() + float(wait_s)
    while time.monotonic() < t_end and not should_stop():
        try:
            if (driver_b.find_elements(AppiumBy.ID, B_CALL_ROOT_ID) or
                driver_b.find_elements(AppiumBy.ID, B_ANSWER_ROOT_ID) or
                driver_b.find_elements(AppiumBy.ID, B_ACCEPT_CONTAINER_ID) or
                driver_b.find_elements(AppiumBy.ID, B_ACCEPT_SWIPE_HINT_ID) or
                driver_b.find_elements(AppiumBy.ID, B_ACCEPT_BUTTON_ID)):
                return True
        except:
            pass
        time.sleep(0.2)
    return False

def b_ui_incoming_present(driver_b):
    try:
        return bool(
            driver_b.find_elements(AppiumBy.ID, B_CALL_ROOT_ID) or
            driver_b.find_elements(AppiumBy.ID, B_ANSWER_ROOT_ID) or
            driver_b.find_elements(AppiumBy.ID, B_ACCEPT_CONTAINER_ID) or
            driver_b.find_elements(AppiumBy.ID, B_ACCEPT_SWIPE_HINT_ID) or
            driver_b.find_elements(AppiumBy.ID, B_ACCEPT_BUTTON_ID)
        )
    except:
        return False

def wait_b_ui_clear(driver_b, steady_s=1.5, timeout_s=8.0):
    t_end = time.monotonic() + float(timeout_s)
    cleared_since = None
    while time.monotonic() < t_end and not should_stop():
        present = b_ui_incoming_present(driver_b)
        if present:
            cleared_since = None
        else:
            if cleared_since is None:
                cleared_since = time.monotonic()
            elif (time.monotonic() - cleared_since) >= float(steady_s):
                return True
        time.sleep(0.2)
    return False

def answer_incoming_call_b(driver_b, wait_s=WAIT_INCOMING_B_S):
    if not wait_incoming_on_b(driver_b, wait_s=wait_s):
        return False, None
    START_X, START_Y = 540, 1918
    END_Y = 273
    def accepted_now():
        try:
            still = driver_b.find_elements(AppiumBy.ID, "com.whatsapp:id/accept_incoming_call_view")
            return not bool(still)
        except:
            return False
    try:
        btns = driver_b.find_elements(AppiumBy.ID, "com.whatsapp:id/accept_incoming_call_view")
        if btns:
            btns[0].click()
            time.sleep(0.4)
            if accepted_now(): return True, True
    except: pass
    try:
        containers = driver_b.find_elements(AppiumBy.ID, B_ACCEPT_CONTAINER_ID)
        if containers:
            _drag_up_via_gesture(driver_b, containers[0], pct=0.75, duration=850)
            time.sleep(0.5)
            if accepted_now(): return True, True
    except: pass
    try:
        driver_b.execute_script("mobile: dragGesture", {
            "startX": int(START_X), "startY": int(START_Y),
            "endX": int(START_X), "endY": int(END_Y),
            "duration": 900
        })
        time.sleep(0.6)
        if accepted_now(): return True, True
    except: pass
    try:
        _w3c_swipe_up(driver_b, START_X, START_Y, END_Y, hold_ms=350, move_ms=900)
        time.sleep(0.6)
        if accepted_now(): return True, True
    except: pass
    t_end = time.monotonic() + float(wait_s)
    while time.monotonic() < t_end and not should_stop():
        if accepted_now(): return True, True
        time.sleep(0.2)
    return False, None

# ====== LOG / MÉTRICAS ======
DEBUG = True
CALL_ID = 0
def log_evt(k: str, when: datetime | None = None, extra: str = ""):
    if not DEBUG: return
    if when is None: when = datetime.now()
    ts = when.strftime("%H:%M:%S")
    print(f"[DBG] [EVT] {k} @ {ts}{(' | '+extra) if extra else ''}")

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

# ====== RUN LLAMAR ======
def is_reconnecting(txt: str) -> bool:
    t = (txt or "").lower()
    return any(tok in t for tok in RECON_TOKENS)

def run_llamar(driver_a, driver_b, contacto,
               hold_s=CDR_HOLD_S, drop_grace=DROP_GRACE_S,
               auto_answer_b=True):
    global CALL_ID
    if should_stop(): return
    if driver_b is None:
        auto_answer_b = False
    try:
        preflight_device(driver_a, APP_PKG)
        if driver_b is not None: preflight_device(driver_b, APP_PKG)

        ok = ensure_chat_open(driver_a, contacto)
        if not ok:
            tnow_a = device_now(driver_a)
            csv_write_device(csvw_a, driver_a, "CDR", CALL_ID, contacto,
                             tnow_a, tnow_a, "Failed", "ChatNotFound", checkpoint=True)
            log_evt("CDR_FAIL", tnow_a, "ChatNotFound"); return
        if should_stop(): colgar_seguro(driver_a); return

        CALL_ID += 1
        try:
            tocar_boton_llamar(driver_a)
        except Exception as e:
            t_err_a = device_now(driver_a)
            csv_write_device(csvw_a, driver_a, "CDR", CALL_ID, contacto,
                             t_err_a, t_err_a, "Failed", f"NoCallBtn:{e}", checkpoint=True)
            log_evt("CDR_FAIL", t_err_a, f"NoCallBtn:{e}"); return

        t_press_a = device_now(driver_a)
        csv_write_device(csvw_a, driver_a, "CALL_ATTEMPT", CALL_ID, contacto,
                         t_press_a, t_press_a, "Event", "", "by=A")
        log_evt("CALL_ATTEMPT", t_press_a, "by=A")

        b_incoming = False
        if (driver_b is not None) and (not should_stop()):
            b_incoming = wait_incoming_on_b(driver_b, wait_s=WAIT_INCOMING_B_S)
            if b_incoming and (csvw_b is not None):
                t_in_b = device_now(driver_b)
                csv_write_device(csvw_b, driver_b, "B_INCOMING", CALL_ID, contacto,
                                 t_in_b, t_in_b, "Event", "", "incoming_ui=visible")

        answered_dt_a = None
        if (driver_b is not None) and auto_answer_b and (not should_stop()):
            answered, _ = answer_incoming_call_b(driver_b, wait_s=5 if b_incoming else WAIT_INCOMING_B_S)
            if answered and (csvw_b is not None):
                t_ans_b = device_now(driver_b)
                csv_write_device(csvw_b, driver_b, "B_ANSWER", CALL_ID, contacto,
                                 t_ans_b, t_ans_b, "Event", "")
                answered_dt_a = device_now(driver_a)
                log_evt("B_ANSWER", answered_dt_a)

        connected_dt_a = None
        t_deadline = time.monotonic() + 25.0
        while time.monotonic() < t_deadline and not should_stop():
            txt = find_subtitle_text(driver_a)
            if is_no_answer_text(txt) or has_no_answer_cta(driver_a):
                now_a = device_now(driver_a)
                csv_write_device(csvw_a, driver_a, "CDR", CALL_ID, contacto,
                                 t_press_a, now_a, "Failed", "NoAnswer", checkpoint=True)
                log_evt("CDR_FAIL", now_a, f"NoAnswer | subtitle={txt!r}")
                colgar_seguro(driver_a); return
            if _CONNECTED_RE.match(txt or ""):
                connected_dt_a = device_now(driver_a)
                extra_parts = [f"since_attempt_s={(connected_dt_a - t_press_a).total_seconds():.2f}"]
                if answered_dt_a:
                    extra_parts.append(f"since_answer_s={(connected_dt_a - answered_dt_a).total_seconds():.2f}")
                csv_write_device(csvw_a, driver_a, "CALL_CONNECTED", CALL_ID, contacto,
                                 connected_dt_a, connected_dt_a, "Event", "", ";".join(extra_parts))
                log_evt("CALL_CONNECTED", connected_dt_a, "; ".join(extra_parts))
                break
            time.sleep(0.2)

        if should_stop(): colgar_seguro(driver_a); return
        if not connected_dt_a:
            now_a = device_now(driver_a)
            csv_write_device(csvw_a, driver_a, "CDR", CALL_ID, contacto,
                             t_press_a, now_a, "Failed", "NotConnected", checkpoint=True)
            log_evt("CDR_FAIL", now_a, "NotConnected")
            colgar_seguro(driver_a); return

        recon_spans_A, recon_spans_B = [], []
        recon_active_A = recon_active_B = False
        recon_start_A  = recon_start_B  = None

        def _recon_update(side, cur_txt: str):
            nonlocal recon_active_A, recon_active_B, recon_start_A, recon_start_B
            if side == 'A':
                is_rec = is_reconnecting(cur_txt)
                if is_rec and not recon_active_A:
                    recon_active_A = True; recon_start_A = device_now(driver_a)
                    if DEBUG: print(f"[DBG] [EVT] RECON_A start @ {recon_start_A.strftime('%H:%M:%S')}")
                elif (not is_rec) and recon_active_A:
                    recon_active_A = False; end_dt = device_now(driver_a)
                    recon_spans_A.append((recon_start_A, end_dt))
                    if DEBUG: print(f"[DBG] [EVT] RECON_A end @ {end_dt.strftime('%H:%M:%S')} | dur={(end_dt - recon_start_A).total_seconds():.2f}s")
                    recon_start_A = None
            else:
                if driver_b is None: return
                is_rec = is_reconnecting(cur_txt)
                if is_rec and not recon_active_B:
                    recon_active_B = True; recon_start_B = device_now(driver_b)
                    if DEBUG: print(f"[DBG] [EVT] RECON_B start @ {recon_start_B.strftime('%H:%M:%S')}")
                elif (not is_rec) and recon_active_B:
                    recon_active_B = False; end_dt = device_now(driver_b)
                    recon_spans_B.append((recon_start_B, end_dt))
                    if DEBUG: print(f"[DBG] [EVT] RECON_B end @ {end_dt.strftime('%H:%M:%S')} | dur={(end_dt - recon_start_B).total_seconds():.2f}s")
                    recon_start_B = None

        hold_deadline = time.monotonic() + float(hold_s)
        missing_since = None
        dropped = False

        while time.monotonic() < hold_deadline and not should_stop():
            alive_A = False; txt_A = ""
            try:
                txt_A = find_subtitle_text(driver_a)
                if txt_A: alive_A = True
            except: alive_A = False

            alive_B = False; txt_B = ""
            if driver_b is not None:
                try:
                    txt_B = find_subtitle_text(driver_b)
                    if txt_B: alive_B = True
                except:
                    alive_B = False

            try:
                _recon_update('A', txt_A if alive_A else "")
                _recon_update('B', txt_B if alive_B else "")
            except:
                pass

            if alive_A:
                missing_since = None
            else:
                if missing_since is None:
                    missing_since = time.monotonic()
                elif (time.monotonic() - missing_since) >= float(drop_grace):
                    dropped = True; break
            time.sleep(0.25)

        if recon_active_A and recon_start_A is not None:
            end_dt_tmp = device_now(driver_a)
            recon_spans_A.append((recon_start_A, end_dt_tmp))
            if DEBUG: print(f"[DBG] [EVT] RECON_A end(forced) @ {end_dt_tmp.strftime('%H:%M:%S')} | dur={(end_dt_tmp - recon_start_A).total_seconds():.2f}s")
        if (driver_b is not None) and recon_active_B and (recon_start_B is not None):
            end_dt_tmp = device_now(driver_b)
            recon_spans_B.append((recon_start_B, end_dt_tmp))
            if DEBUG: print(f"[DBG] [EVT] RECON_B end(forced) @ {end_dt_tmp.strftime('%H:%M:%S')} | dur={(end_dt_tmp - recon_start_B).total_seconds():.2f}s")

        end_a = device_now(driver_a)

        if dropped:
            held_est = int(hold_s - max(0, hold_deadline - time.monotonic()))
            csv_write_device(csvw_a, driver_a, "CDR", CALL_ID, contacto,
                             t_press_a, end_a, "Failed", "Dropped",
                             f"held_s≈{held_est}", checkpoint=True)
            log_evt("CDR_DROPPED", end_a)
        else:
            csv_write_device(csvw_a, driver_a, "CDR", CALL_ID, contacto,
                             t_press_a, end_a, "Successful", "",
                             f"held_s={int(hold_s)}", checkpoint=True)
            log_evt("CDR_END", end_a, f"held_s={int(hold_s)}")

        csv_write_device(csvw_a, driver_a, "RECON_COUNT", CALL_ID, contacto,
                         t_press_a, end_a, "Info", "",
                         f"count={len(recon_spans_A)};side=A")
        for (rs, re_) in recon_spans_A:
            secs = (re_ - rs).total_seconds()
            csv_write_device(csvw_a, driver_a, "RECON", CALL_ID, contacto,
                             rs, re_, "Span", "", f"seconds={secs:.2f};side=A")

        if (driver_b is not None) and (csvw_b is not None):
            t_mark_b = device_now(driver_b)
            csv_write_device(csvw_b, driver_b, "RECON_COUNT_B", CALL_ID, contacto,
                             t_mark_b, t_mark_b, "Info", "",
                             f"count={len(recon_spans_B)};side=B")
            for (rs, re_) in recon_spans_B:
                secs = (re_ - rs).total_seconds()
                csv_write_device(csvw_b, driver_b, "RECON_B", CALL_ID, contacto,
                                 rs, re_, "Span", "", f"seconds={secs:.2f};side=B")
        colgar_seguro(driver_a)
    finally:
        try:
            set_config_param(PLAN_PATH_RUNTIME, 'call_id', str(CALL_ID))
        except:
            pass

# ====== ROL B STAND-ALONE ======
def run_b_standalone(driver_b, hold_s=CDR_HOLD_S, drop_grace=DROP_GRACE_S):
    local_call_id = 0
    while not should_stop():
        wait_b_ui_clear(driver_b, steady_s=1.0, timeout_s=5.0)
        incoming = wait_incoming_on_b(driver_b, wait_s=WAIT_INCOMING_B_S)
        if not incoming:
            time.sleep(0.5); continue

        local_call_id += 1
        t_in_b = device_now(driver_b)
        csv_write_device(csvw_b, driver_b, "B_INCOMING", local_call_id, CONTACTO,
                         t_in_b, t_in_b, "Event", "", "incoming_ui=visible")
        log_evt("B_INCOMING", t_in_b, f"call={local_call_id}")

        answered, _ = answer_incoming_call_b(driver_b, wait_s=5)
        if not answered:
            t_now = device_now(driver_b)
            csv_write_device(csvw_b, driver_b, "CDR_B", local_call_id, CONTACTO,
                             t_in_b, t_now, "Failed", "NoAnswer", checkpoint=True)
            log_evt("CDR_B_FAIL", t_now, "NoAnswer")
            wait_b_ui_clear(driver_b, steady_s=1.0, timeout_s=5.0)
            time.sleep(3.0)
            continue

        t_ans_b = device_now(driver_b)
        csv_write_device(csvw_b, driver_b, "B_ANSWER", local_call_id, CONTACTO,
                         t_ans_b, t_ans_b, "Event", "")

        recon_spans_B = []; recon_active_B = False; recon_start_B = None
        def _recon_update_b(cur_txt: str):
            nonlocal recon_active_B, recon_start_B
            is_rec = is_reconnecting(cur_txt)
            if is_rec and not recon_active_B:
                recon_active_B = True; recon_start_B = device_now(driver_b)
                if DEBUG: print(f"[DBG] [EVT] RECON_B start @ {recon_start_B.strftime('%H:%M:%S')}")
            elif (not is_rec) and recon_active_B:
                recon_active_B = False; end_dt = device_now(driver_b)
                recon_spans_B.append((recon_start_B, end_dt))
                if DEBUG: print(f"[DBG] [EVT] RECON_B end @ {end_dt.strftime('%H:%M:%S')} | dur={(end_dt - recon_start_B).total_seconds():.2f}s")
                recon_start_B = None

        hold_deadline = time.monotonic() + float(hold_s)
        missing_since = None; dropped = False
        while time.monotonic() < hold_deadline and not should_stop():
            alive_B = False; txt_B = ""
            try:
                txt_B = find_subtitle_text(driver_b)
                if txt_B: alive_B = True
            except: alive_B = False
            try:
                _recon_update_b(txt_B if alive_B else "")
            except: pass
            if alive_B:
                missing_since = None
            else:
                if missing_since is None:
                    missing_since = time.monotonic()
                elif (time.monotonic() - missing_since) >= float(drop_grace):
                    dropped = True; break
            time.sleep(0.25)

        if recon_active_B and (recon_start_B is not None):
            end_dt_tmp = device_now(driver_b)
            recon_spans_B.append((recon_start_B, end_dt_tmp))
            if DEBUG: print(f"[DBG] [EVT] RECON_B end(forced) @ {end_dt_tmp.strftime('%H:%M:%S')} | dur={(end_dt_tmp - recon_start_B).total_seconds():.2f}s")

        end_b = device_now(driver_b)
        if dropped:
            held_est = int(hold_s - max(0, hold_deadline - time.monotonic()))
            csv_write_device(csvw_b, driver_b, "CDR_B", local_call_id, CONTACTO,
                             t_ans_b, end_b, "Failed", "Dropped",
                             f"held_s≈{held_est}", checkpoint=True)
            log_evt("CDR_B_DROPPED", end_b)
        else:
            csv_write_device(csvw_b, driver_b, "CDR_B", local_call_id, CONTACTO,
                             t_ans_b, end_b, "Successful", "",
                             f"held_s={int(hold_s)}", checkpoint=True)
            log_evt("CDR_B_END", end_b, f"held_s={int(hold_s)}")

        t_mark_b = device_now(driver_b)
        csv_write_device(csvw_b, driver_b, "RECON_COUNT_B", local_call_id, CONTACTO,
                         t_mark_b, t_mark_b, "Info", "",
                         f"count={len(recon_spans_B)};side=B")
        for (rs, re_) in recon_spans_B:
            secs = (re_ - rs).total_seconds()
            csv_write_device(csvw_b, driver_b, "RECON_B", local_call_id, CONTACTO,
                             rs, re_, "Span", "", f"seconds={secs:.2f};side=B")

        wait_b_ui_clear(driver_b, steady_s=1.0, timeout_s=5.0)
        time.sleep(3.0)

# ====== LECTURA DEL PLAN ======
def leer_plan_config(path_txt: str):
    global TIEMPO_ENTRE_CICLOS, CONTACTO, CDR_HOLD_S, CALL_ID, ROLE_CONFIG
    seccion = None
    pruebas_norm = []
    last_act = None

    def normaliza_prueba(linea: str):
        s = linea.strip().lower()
        s = s.replace('+', ' y ')
        s = ' '.join(s.split())
        if ('llamar' in s) or ('llamada' in s) or ('run' in s):
            return 'run_llamar'
        if 'cdr' in s:
            return 'cdr'
        if ('cst' in s) and ('csfr' in s):
            return 'cst_csfr'
        return None

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
                    act = None
                    cnt = None
                    if parts:
                        if parts[0].isdigit():
                            cnt = int(parts[0])
                            act = last_act or 'run_llamar'
                        else:
                            act = normaliza_prueba(parts[0]) or last_act or 'run_llamar'
                            if len(parts) > 1 and parts[1].isdigit():
                                cnt = int(parts[1])
                    if cnt is None:
                        cnt = 1
                    for _ in range(max(0, cnt)):
                        pruebas_norm.append(act)
                    last_act = act
                    continue

                act = normaliza_prueba(s)
                if act:
                    pruebas_norm.append(act)
                    last_act = act
                continue

    return pruebas_norm


# ====== MAIN ======
def main():
    global CONTACTO, CDR_HOLD_S, UDID_A_RUNTIME, UDID_B_RUNTIME
    global UDID_A, UDID_B, APPIUM_URL_A, APPIUM_URL_B, SYSTEM_PORT_A, SYSTEM_PORT_B
    args = parse_args()

    plan_path = args.plan or PLAN_TXT
    pruebas = leer_plan_config(plan_path)

    role = ROLE_CONFIG
    if args.role is not None:
        role = args.role

    if args.contacto: CONTACTO = args.contacto
    if args.hold is not None: CDR_HOLD_S = int(args.hold)
    wait_between = TIEMPO_ENTRE_CICLOS
    if args.tiempo_entre_ciclos is not None:
        wait_between = float(args.tiempo_entre_ciclos)
    if args.udid_a: UDID_A = args.udid_a
    if args.udid_b: UDID_B = args.udid_b
    if args.appium_url_a: APPIUM_URL_A = args.appium_url_a
    if args.appium_url_b: APPIUM_URL_B = args.appium_url_b
    if args.system_port_a: SYSTEM_PORT_A = int(args.system_port_a)
    if args.system_port_b: SYSTEM_PORT_B = int(args.system_port_b)

    UDID_A_RUNTIME = UDID_A
    UDID_B_RUNTIME = UDID_B

    csv_init(UDID_A, UDID_B, role=role)

    driver_a = driver_b = None
    try:
        if role in ("both", "A"):
            driver_a = build_driver(APPIUM_URL_A, UDID_A, SYSTEM_PORT_A, force_launch=True)
            preflight_device(driver_a, APP_PKG)
        if role in ("both", "B"):
            driver_b = build_driver(APPIUM_URL_B, UDID_B, SYSTEM_PORT_B, force_launch=(role=="B"))
            preflight_device(driver_b, APP_PKG)

        if role == "B":
            print("[RUN] B stand-alone esperando llamadas entrantes...")
            run_b_standalone(driver_b, hold_s=CDR_HOLD_S, drop_grace=DROP_GRACE_S)
            return

        if role in ("A", "both"):
            if not driver_a:
                print("[ERR] Rol A requerido para ejecutar el plan."); return
            if role == "both" and not driver_b:
                print("[ERR] Rol both requiere B."); return

            if not pruebas:
                print("[WARN] No hay pruebas en el plan.")
            for i, accion in enumerate(pruebas, 1):
                if should_stop(): break
                print(f"[RUN] Comenzando {accion.upper()} para '{CONTACTO}'...")

                if accion == 'run_llamar':
                    run_llamar(driver_a, driver_b, CONTACTO,
                               hold_s=CDR_HOLD_S, drop_grace=DROP_GRACE_S,
                               auto_answer_b=(driver_b is not None))
                elif accion == 'cst_csfr':
                    print("Se encuentra comentado")
                elif accion == 'cdr':
                    print("Se encuentra comentado")

                print(f"[RUN] Terminada {accion.upper()}")
                if i < len(pruebas) and not should_stop():
                    print(f"[RUN] Esperando {wait_between}s...")
                    try:
                        time.sleep(float(wait_between))
                    except Exception:
                        pass
    finally:
        try:
            if driver_a: colgar_seguro(driver_a)
        except: pass
        time.sleep(0.5)
        for d in (driver_a, driver_b):
            try:
                if d: d.quit()
            except: pass
        for w in (csvw_a, csvw_b, csvw_all):
            try:
                if w: w.close()
            except: pass

if __name__ == "__main__":
    main()
