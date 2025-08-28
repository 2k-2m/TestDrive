# -*- coding: utf-8 -*-
import os, csv, time, re, signal
from datetime import datetime

from appium import webdriver
from appium.webdriver.common.appiumby import AppiumBy
from appium.options.android import UiAutomator2Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# =========================
# Rutas/plan
# =========================
PLAN_TXT = os.path.join(os.path.dirname(__file__), "configuracion.txt")

# =========================
# CONFIG
# =========================
# Dispositivo A (caller)
UDID_A = "6NUDU18529000033"
APPIUM_URL_A = "http://127.0.0.1:4723"
SYSTEM_PORT_A = 8206

# Dispositivo B (observer / podrá contestar en CDR)
UDID_B = "6NU7N18614004267"
APPIUM_URL_B = "http://127.0.0.1:4726"
SYSTEM_PORT_B = 8212

APP_PKG = "com.whatsapp"
APP_ACT = "com.whatsapp.HomeActivity"

# Variables cargadas desde el plan
CONTACTO = "0"
TIEMPO_ENTRE_CICLOS = 0

def leer_plan_config(path_txt: str):
    global TIEMPO_ENTRE_CICLOS, CONTACTO

    seccion = None
    pruebas_norm = []

    def normaliza_prueba(linea: str):
        s = linea.strip().lower()
        s = s.replace('+', ' y ')
        s = ' '.join(s.split())
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
                if h.startswith('PARAM'):   seccion = 'PARAM'
                elif h.startswith('CONTACTO'): seccion = 'CONTACTO'
                elif h.startswith('PRUEBA'):  seccion = 'PRUEBA'
                else: seccion = None
                continue

            if seccion == 'PARAM':
                if '=' in line:
                    k, v = line.split('=', 1)
                    k = k.strip().lower()
                    v = v.strip()
                    if k == 'tiempo_entre_ciclos':
                        try:
                            TIEMPO_ENTRE_CICLOS = int(v)
                        except ValueError:
                            try:
                                TIEMPO_ENTRE_CICLOS = float(v)
                            except ValueError:
                                TIEMPO_ENTRE_CICLOS = 0
                continue

            if seccion == 'CONTACTO':
                if line:
                    CONTACTO = line.strip()
                continue

            if seccion == 'PRUEBA':
                act = normaliza_prueba(line)
                if act:
                    pruebas_norm.append(act)
                continue

    return pruebas_norm

# =========================
# Timeouts / parámetros
# =========================
CST_TIMEOUT_S  = 20.0
CSFR_TIMEOUT_S = 20.0
CDR_HOLD_S     = 15   #Cambiar a la hora esta en segundos
DROP_GRACE_S   = 2.0

# =========================
# CSV
# =========================
BASE_DIR = os.path.dirname(__file__)
timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
CSV_PATH = os.path.join(BASE_DIR, f"WhatsApp_KPIs_{timestamp}.csv")
CSV_HEADER = ["App","Network","KPI","Contact","Latitude","Longitude","Start","End","Result","Failure","Extra"]

def csv_init():
    if not os.path.exists(CSV_PATH) or os.path.getsize(CSV_PATH) == 0:
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADER)

def csv_write(kpi, contact, start_dt, end_dt, result, failure="",
              extra="", network="", lat="", lon="", app="WhatsApp"):
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            app, network, kpi, contact,
            lat, lon,
            start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            result, failure, extra
        ])

# =========================
# Drivers
# =========================
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

# =========================
# Utilidades Android
# =========================
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

def obtener_gps(driver):
    try:
        loc = driver.location
        return str(loc.get("latitude","")), str(loc.get("longitude",""))
    except:
        return "", ""

def esperar(drv, cond, t=10):
    return WebDriverWait(drv, t).until(cond)

# =========================
# Selectores
# =========================
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

# =========================
# Señales
# =========================
detener = False
def manejar_senal(sig, frame):
    global detener
    detener = True
signal.signal(signal.SIGINT, manejar_senal)
signal.signal(signal.SIGTERM, manejar_senal)

# =========================
# Navegación / selección
# =========================
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

def ensure_chat_open(driver, contacto: str) -> bool:
    if is_in_chat_with(driver, contacto):
        return True
    if is_in_chats_list(driver):
        if open_chat(driver, contacto):
            return True
    go_to_chats_tab(driver)
    return open_chat(driver, contacto)

# =========================
# Llamada / estados
# =========================
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
    try:
        el = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((
            AppiumBy.XPATH, "//*[contains(@content-desc,'Llam')] | //*[@content-desc[contains(.,'Call')]]"
        )))
        el.click()
    except:
        raise Exception("NoVoiceCallButton")

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

# =========================
# Auto-answer en B
# =========================
def _center(rect):
    return (rect["x"] + rect["width"] // 2, rect["y"] + rect["height"] // 2)

def _point_near_bottom(rect, pct_from_bottom=0.88):
    cx = rect["x"] + rect["width"] // 2
    sy = int(rect["y"] + rect["height"] * pct_from_bottom)
    return cx, sy

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

def _drag_up_via_shell(driver_b, start_x, start_y, end_y, duration_ms=950):
    driver_b.execute_script("mobile: shell", {
        "command": "input",
        "args": ["swipe", str(int(start_x)), str(int(start_y)), str(int(start_x)), str(int(end_y)), str(int(duration_ms))],
        "includeStderr": True,
        "timeout": 5000
    })

def _swipe_up_element_robust(driver_b, el) -> bool:
    r = el.rect
    sx, sy = _point_near_bottom(r, pct_from_bottom=0.88)
    ey = max(0, int(r["y"] + r["height"] * 0.15))
    try:
        _w3c_swipe_up(driver_b, sx, sy, ey, hold_ms=320, move_ms=800)
        time.sleep(0.6)
        return True
    except:
        pass
    try:
        _drag_up_via_gesture(driver_b, el, pct=0.75, duration=850)
        time.sleep(0.5)
        return True
    except:
        pass
    try:
        _drag_up_via_shell(driver_b, sx, sy, ey, duration_ms=950)
        time.sleep(0.5)
        return True
    except:
        pass
    return False

def wake_and_dismiss_keyguard(driver_b):
    try:
        driver_b.execute_script("mobile: shell", {"command":"input","args":["keyevent","224"]})
        driver_b.execute_script("mobile: shell", {"command":"wm","args":["dismiss-keyguard"]})
    except:
        pass

def answer_incoming_call_b(driver_b, wait_s=14):
    def _dbg(s): 
        if DEBUG: 
            print(f"[DBG] {s}")

    try:
        wake_and_dismiss_keyguard(driver_b)
    except:
        pass

    START_X, START_Y = 540, 1918
    END_X,   END_Y   = 540, 273
    t_end = time.monotonic() + wait_s

    def accepted_now_dt():
        """Si ya no vemos el botón de aceptar, asumimos que contestó ahora y devolvemos ese datetime."""
        try:
            still = driver_b.find_elements(AppiumBy.ID, "com.whatsapp:id/accept_incoming_call_view")
            if not still:
                return datetime.now()
        except:
            pass
        return None

    # Click rápido
    try:
        btns = driver_b.find_elements(AppiumBy.ID, "com.whatsapp:id/accept_incoming_call_view")
        if btns:
            btns[0].click()
            time.sleep(0.4)
            dt = accepted_now_dt()
            if dt:
                _dbg("B contestó (tap).")
                return True, dt
    except:
        pass

    # dragGesture
    try:
        _dbg("B intenta contestar (dragGesture coords).")
        driver_b.execute_script("mobile: dragGesture", {
            "startX": int(START_X), "startY": int(START_Y),
            "endX":   int(END_X),   "endY":   int(END_Y),
            "duration": 900
        })
        time.sleep(0.6)
        dt = accepted_now_dt()
        if dt:
            return True, dt
    except:
        pass

    # W3C actions
    try:
        _dbg("B intenta contestar (W3C actions).")
        actions = [{
            "type": "pointer","id": "finger1","parameters": {"pointerType": "touch"},
            "actions": [
                {"type": "pointerMove","duration": 0,"x": int(START_X),"y": int(START_Y)},
                {"type": "pointerDown","button": 0},
                {"type": "pause","duration": 350},
                {"type": "pointerMove","duration": 900,"x": int(END_X),"y": int(END_Y)},
                {"type": "pointerUp","button": 0},
            ],
        }]
        driver_b.perform_actions(actions)
        try: driver_b.release_actions()
        except: pass
        time.sleep(0.6)
        dt = accepted_now_dt()
        if dt:
            return True, dt
    except:
        pass

    # Poll final
    while time.monotonic() < t_end:
        dt = accepted_now_dt()
        if dt:
            return True, dt
        time.sleep(0.2)

    return False, None



# =========================
# Métricas
# =========================
def measure_cst_csfr(driver_a, driver_b, contacto,
                     cst_timeout=CST_TIMEOUT_S,
                     csfr_timeout=CSFR_TIMEOUT_S):
    network = obtener_red_real(driver_a)
    lat, lon = obtener_gps(driver_a)
    t0_dt = datetime.now()

    if not ensure_chat_open(driver_a, contacto):
        now_dt = datetime.now()
        csv_write("CST",  contacto, t0_dt, now_dt, "Failed", "ChatNotFound", network=network, lat=lat, lon=lon)
        csv_write("CSFR", contacto, t0_dt, now_dt, "Failed", "ChatNotFound", network=network, lat=lat, lon=lon)
        return

    try:
        tocar_boton_llamar(driver_a)
    except Exception as e:
        now_dt = datetime.now()
        err = f"NoCallBtn:{e}"
        csv_write("CST",  contacto, t0_dt, now_dt, "Failed", err, network=network, lat=lat, lon=lon)
        csv_write("CSFR", contacto, t0_dt, now_dt, "Failed", err, network=network, lat=lat, lon=lon)
        return

    press_t = time.monotonic()
    deadline_cst  = press_t + float(cst_timeout)
    deadline_csfr = press_t + float(csfr_timeout)

    cst_done = False; cst_t = None; cst_trigger = ""
    connected_t = None
    while time.monotonic() < deadline_cst and not detener:
        txt = find_subtitle_text(driver_a)
        if any(k in (txt or "") for k in SUBTITLE_POSITIVES):
            cst_done = True; cst_t = time.monotonic(); cst_trigger = "label"
            break
        if _CONNECTED_RE.match(txt or ""):
            connected_t = time.monotonic()
        time.sleep(0.15)
    if not cst_done and connected_t:
        cst_done = True; cst_t = connected_t; cst_trigger = "connected"

    csfr_done = False
    while time.monotonic() < deadline_csfr and not detener:
        try:
            if (driver_b.find_elements(AppiumBy.ID, B_CALL_ROOT_ID) or
                driver_b.find_elements(AppiumBy.ID, B_ANSWER_ROOT_ID) or
                driver_b.find_elements(AppiumBy.ID, B_ACCEPT_CONTAINER_ID) or
                driver_b.find_elements(AppiumBy.ID, B_ACCEPT_SWIPE_HINT_ID) or
                driver_b.find_elements(AppiumBy.ID, B_ACCEPT_BUTTON_ID)):
                csfr_done = True
                break
        except:
            pass
        time.sleep(0.15)

    end_dt = datetime.now()

    if cst_done and cst_t is not None:
        cst_val = max(0.0, cst_t - press_t)
        csv_write("CST", contacto, t0_dt, end_dt, "Successful", "",
                  f"setup_s={cst_val:.2f};trigger=A:{cst_trigger}",
                  network=network, lat=lat, lon=lon)
    else:
        causa = "NoSetupLabel" if network != "Disconnected" else "NoService"
        csv_write("CST", contacto, t0_dt, end_dt, "Failed", causa, "", network=network, lat=lat, lon=lon)

    if csfr_done:
        csv_write("CSFR", contacto, t0_dt, end_dt, "Successful", "", "incoming_on_B:fullscreen",
                  network=network, lat=lat, lon=lon)
    else:
        csv_write("CSFR", contacto, t0_dt, end_dt, "Failed", "NoIncomingOnB", "",
                  network=network, lat=lat, lon=lon)

    colgar_seguro(driver_a)






#def measure_cst_csfr(driver_a, driver_b, contacto)
DEBUG = True
RECON_TOKEN = "reconectando"

def _save_pagesource(driver, tag="ps"):
    try:
        xml = driver.page_source
        fn = f"./_debug_{tag}_{int(time.time())}.xml"
        with open(fn, "w", encoding="utf-8") as f:
            f.write(xml)
        log(f"pageSource guardado en {fn}")
    except Exception as e:
        log(f"no pude guardar pageSource: {e}")

def log(msg):
    if DEBUG:
        print(f"[DBG] {msg}")


def measure_cdr(driver_a, driver_b, contacto,
                hold_s=CDR_HOLD_S, drop_grace=DROP_GRACE_S,
                auto_answer_b=True):

    # 1) Abrir chat
    ok = ensure_chat_open(driver_a, contacto)
    if not ok:
        _save_pagesource(driver_a, "cdr_chatnotfound")
        tnow = datetime.now()
        network = obtener_red_real(driver_a)
        lat, lon = obtener_gps(driver_a)
        csv_write("CDR", contacto, tnow, tnow, "Failed", "ChatNotFound", "", network, lat, lon)
        log_evt("CDR_FAIL", tnow, "ChatNotFound")
        return

    # 2) Contexto
    network = obtener_red_real(driver_a)
    lat, lon = obtener_gps(driver_a)

    # 3) CALL_ATTEMPT (al presionar botón)
    try:
        tocar_boton_llamar(driver_a)
    except Exception as e:
        t_err = datetime.now()
        csv_write("CDR", contacto, t_err, t_err, "Failed", f"NoCallBtn:{e}", "", network, lat, lon)
        log_evt("CDR_FAIL", t_err, f"NoCallBtn:{e}")
        return

    t_press_dt = datetime.now()
    csv_write("CALL_ATTEMPT", contacto, t_press_dt, t_press_dt, "Event", "", "by=A", network, lat, lon)
    log_evt("CALL_ATTEMPT", t_press_dt, "by=A")

    # El CDR empieza en el intento:
    t0_dt = t_press_dt

    # 4) B_ANSWER (si hay auto-answer)
    answered_dt = None
    if auto_answer_b:
        answered, answered_dt = answer_incoming_call_b(driver_b, wait_s=14)
        if answered and answered_dt:
            csv_write("B_ANSWER", contacto, answered_dt, answered_dt, "Event", "", "", network, lat, lon)
            log_evt("B_ANSWER", answered_dt)

    # 5) CALL_CONNECTED (cuando A muestra mm:ss en subtítulo)
    connected_dt = None
    t_deadline = time.monotonic() + 25.0
    while time.monotonic() < t_deadline and not detener:
        txt = find_subtitle_text(driver_a)  # ya viene lowercase
        if _CONNECTED_RE.match(txt or ""):
            connected_dt = datetime.now()
            extra_parts = [f"since_attempt_s={(connected_dt - t_press_dt).total_seconds():.2f}"]
            if answered_dt:
                extra_parts.append(f"since_answer_s={(connected_dt - answered_dt).total_seconds():.2f}")
                csv_write("ANSWER_TO_CONNECTED", contacto, answered_dt, connected_dt, "Metric", "",
                          f"seconds={(connected_dt - answered_dt).total_seconds():.2f}", network, lat, lon)
            csv_write("CALL_CONNECTED", contacto, connected_dt, connected_dt, "Event", "", ";".join(extra_parts),
                      network, lat, lon)
            log_evt("CALL_CONNECTED", connected_dt, "; ".join(extra_parts))
            break
        time.sleep(0.2)

    if not connected_dt:
        now_dt = datetime.now()
        csv_write("CDR", contacto, t0_dt, now_dt, "Failed", "NotConnected", "", network, lat, lon)
        log_evt("CDR_FAIL", now_dt, "NotConnected")
        colgar_seguro(driver_a)
        return

    # -------- Reconectando A/B durante el hold --------
    recon_spans_A, recon_spans_B = [], []
    recon_active_A = recon_active_B = False
    recon_start_A = recon_start_B = None

    def _recon_update(side, cur_txt: str):
        nonlocal recon_active_A, recon_active_B, recon_start_A, recon_start_B
        is_recon = (cur_txt or "").find(RECON_TOKEN) != -1
        if side == 'A':
            if is_recon and not recon_active_A:
                recon_active_A = True
                recon_start_A = datetime.now()
                log("[DBG] [EVT] RECON_A start @ " + recon_start_A.strftime("%H:%M:%S") if DEBUG else "")
            elif (not is_recon) and recon_active_A:
                recon_active_A = False
                end_dt = datetime.now()
                recon_spans_A.append((recon_start_A, end_dt))
                if DEBUG:
                    print(f"[DBG] [EVT] RECON_A end @ {end_dt.strftime('%H:%M:%S')} | dur={(end_dt - recon_start_A).total_seconds():.2f}s")
                recon_start_A = None
        else:
            if is_recon and not recon_active_B:
                recon_active_B = True
                recon_start_B = datetime.now()
                log("[DBG] [EVT] RECON_B start @ " + recon_start_B.strftime("%H:%M:%S") if DEBUG else "")
            elif (not is_recon) and recon_active_B:
                recon_active_B = False
                end_dt = datetime.now()
                recon_spans_B.append((recon_start_B, end_dt))
                if DEBUG:
                    print(f"[DBG] [EVT] RECON_B end @ {end_dt.strftime('%H:%M:%S')} | dur={(end_dt - recon_start_B).total_seconds():.2f}s")
                recon_start_B = None

    hold_deadline = time.monotonic() + float(hold_s)
    missing_since = None
    dropped = False

    while time.monotonic() < hold_deadline and not detener:
        # A
        alive_A = False
        txt_A = ""
        try:
            txt_A = find_subtitle_text(driver_a)
            if txt_A:
                alive_A = True
        except:
            alive_A = False

        # B
        alive_B = False
        txt_B = ""
        try:
            txt_B = find_subtitle_text(driver_b)
            if txt_B:
                alive_B = True
        except:
            alive_B = False

        # Recon en ambos
        try:
            _recon_update('A', txt_A if alive_A else "")
            _recon_update('B', txt_B if alive_B else "")
        except:
            pass

        # Drop por desaparición de UI en A
        if alive_A:
            missing_since = None
        else:
            if missing_since is None:
                missing_since = time.monotonic()
            elif (time.monotonic() - missing_since) >= float(drop_grace):
                dropped = True
                break

        time.sleep(0.25)

    # Cerrar spans si el hold termina mostrando reconectando
    if recon_active_A and recon_start_A is not None:
        end_dt_tmp = datetime.now()
        recon_spans_A.append((recon_start_A, end_dt_tmp))
        if DEBUG:
            print(f"[DBG] [EVT] RECON_A end(forced) @ {end_dt_tmp.strftime('%H:%M:%S')} | dur={(end_dt_tmp - recon_start_A).total_seconds():.2f}s")
    if recon_active_B and recon_start_B is not None:
        end_dt_tmp = datetime.now()
        recon_spans_B.append((recon_start_B, end_dt_tmp))
        if DEBUG:
            print(f"[DBG] [EVT] RECON_B end(forced) @ {end_dt_tmp.strftime('%H:%M:%S')} | dur={(end_dt_tmp - recon_start_B).total_seconds():.2f}s")

    end_dt = datetime.now()

    # Línea principal CDR
    if dropped:
        csv_write("CDR", contacto, t0_dt, end_dt, "Failed", "Dropped",
                  f"held_s≈{int(hold_s - max(0, hold_deadline - time.monotonic()))}",
                  network, lat, lon)
        log_evt("CDR_DROPPED", end_dt)
    else:
        csv_write("CDR", contacto, t0_dt, end_dt, "Successful", "",
                  f"held_s={int(hold_s)}", network, lat, lon)
        log_evt("CDR_END", end_dt, f"held_s={int(hold_s)}")

    # Totales y spans (A)
    csv_write("RECON_COUNT", contacto, t0_dt, end_dt, "Info", "",
              f"count={len(recon_spans_A)};side=A", network, lat, lon)
    for (rs, re_) in recon_spans_A:
        secs = (re_ - rs).total_seconds()
        csv_write("RECON", contacto, rs, re_, "Span", "",
                  f"seconds={secs:.2f};side=A", network, lat, lon)

    # Totales y spans (B)
    csv_write("RECON_COUNT_B", contacto, t0_dt, end_dt, "Info", "",
              f"count={len(recon_spans_B)};side=B", network, lat, lon)
    for (rs, re_) in recon_spans_B:
        secs = (re_ - rs).total_seconds()
        csv_write("RECON_B", contacto, rs, re_, "Span", "",
                  f"seconds={secs:.2f};side=B", network, lat, lon)

    colgar_seguro(driver_a)


def log_evt(kpi: str, when: datetime | None = None, extra: str = ""):
    if not DEBUG:
        return
    if when is None:
        when = datetime.now()
    ts = when.strftime("%H:%M:%S")
    msg = f"[EVT] {kpi} @ {ts}"
    if extra:
        msg += f" | {extra}"
    print(f"[DBG] {msg}")


# =========================
# MAIN
# =========================
def main():
    pruebas = leer_plan_config(PLAN_TXT)

    if not pruebas:
        return

    csv_init()

    driver_a = build_driver(APPIUM_URL_A, UDID_A, SYSTEM_PORT_A, force_launch=True)
    driver_b = build_driver(APPIUM_URL_B, UDID_B, SYSTEM_PORT_B, force_launch=False)

    try:
        for i, accion in enumerate(pruebas, 1):
            print(f"[RUN] Comenzando {accion.upper()} para '{CONTACTO}'...")
            if accion == 'cst_csfr':
                measure_cst_csfr(
                    driver_a, driver_b, CONTACTO,
                    cst_timeout=CST_TIMEOUT_S,
                    csfr_timeout=CSFR_TIMEOUT_S
                )
            elif accion == 'cdr':
                measure_cdr(
                    driver_a, driver_b, CONTACTO,
                    hold_s=CDR_HOLD_S,
                    drop_grace=DROP_GRACE_S,
                    auto_answer_b=True
                )

            print(f"[RUN] Terminada {accion.upper()}")
            if i < len(pruebas):
                print(f"[RUN] Esperando {TIEMPO_ENTRE_CICLOS}s...")
                try:
                    time.sleep(float(TIEMPO_ENTRE_CICLOS))
                except Exception:
                    pass
    finally:
        for d in (driver_a, driver_b):
            try: d.quit()
            except: pass




if __name__ == "__main__":
    main()