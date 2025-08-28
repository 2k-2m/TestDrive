# -*- coding: utf-8 -*-
import os, csv, time, re, threading, signal
from datetime import datetime
from queue import Queue, Empty

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# =========================
# CONFIGURACIÓN BÁSICA
# =========================
# Dispositivo A (caller)
UDID_A = "6NUDU18529000033"
APPIUM_URL_A = "http://127.0.0.1:4723"
SYSTEM_PORT_A = 8206

# Dispositivo B (observer - no contesta)
UDID_B = "6NU7N18614004267"
APPIUM_URL_B = "http://127.0.0.1:4726"
SYSTEM_PORT_B = 8212

APP_PKG = "com.whatsapp"
APP_ACT = "com.whatsapp.HomeActivity"

# Contacto (chat) a llamar
CONTACTO = "vast_wb"

# Timeouts y parámetros de prueba
CST_TIMEOUT_S  = 20.0              # ventana para detectar setup en A
CSFR_TIMEOUT_S = 20.0              # ventana para ver entrante en B
CDR_HOLD_S     = 30.0              # tiempo a sostener la llamada conectada
DROP_GRACE_S   = 2.0               # tolerancia de pérdida de UI antes de marcar drop

# CSV
timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
CSV_PATH = f"./WhatsApp_KPIs_{timestamp}.csv"
CSV_HEADER = ["App","Network","KPI","Contact",
              "Latitude","Longitude",
              "Start","End","Result","Failure","Extra"]

# =========================
# SELECTORES (TU BUILD)
# =========================
# Lista de chats
ROW_IDS = ["com.whatsapp:id/contact_row_container"]
ROW_HEADER_ID = "com.whatsapp:id/conversations_row_header"  # TextViews hijos: nombre visible

# Buscador
SEARCH_BAR_ID = "com.whatsapp:id/my_search_bar"
SEARCH_RESULT_ROW_IDS = ["com.whatsapp:id/contact_row_container"]

# Botón de llamada en el chat
VOICE_CALL_ACCS = ("Llamada",)  # tu content-desc real

# Pantalla de llamada (A)
CALL_HEADER_ID        = "com.whatsapp:id/call_screen_header_view"
CALL_SUBTITLE_ID      = "com.whatsapp:id/subtitle"
CALL_CONTROLS_CARD_ID = "com.whatsapp:id/call_controls_card"
END_CALL_BTN_ID       = "com.whatsapp:id/end_call_button"   # acc: "Abandonar la llamada"

# Entrante en B (fullscreen)
B_CALL_ROOT_ID         = "com.whatsapp:id/call_screen_root"
B_ANSWER_ROOT_ID       = "com.whatsapp:id/answer_call_view_id"
B_ACCEPT_CONTAINER_ID  = "com.whatsapp:id/accept_incoming_call_container"
B_ACCEPT_SWIPE_HINT_ID = "com.whatsapp:id/accept_call_swipe_up_hint_view"
B_ACCEPT_BUTTON_ID     = "com.whatsapp:id/accept_incoming_call_view"

# Palabras y patrón para estado
_CONNECTED_RE      = re.compile(r"^\d{1,2}:\d{2}$")  # 0:00 .. 59:59
SUBTITLE_POSITIVES = ("cifrado", "llamando", "calling", "sonando", "ringing")

# =========================
# ESTADO Y SEÑALES
# =========================
detener = False
def manejar_senal(sig, frame):
    global detener
    print("\n[INFO] Señal recibida, deteniendo con gracia...")
    detener = True
signal.signal(signal.SIGINT, manejar_senal)
signal.signal(signal.SIGTERM, manejar_senal)

# =========================
# CSV
# =========================
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
# ANDROID HELPERS
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
        loc = driver.location  # Appium Settings
        return str(loc.get("latitude","")), str(loc.get("longitude",""))
    except:
        return "", ""

def esperar(drv, cond, t=10):
    return WebDriverWait(drv, t).until(cond)

# =========================
# DRIVERS
# =========================
def setup_driver(url, udid, system_port, force_launch=True):
    caps = {
        "platformName": "Android",
        "automationName": "UiAutomator2",
        "udid": udid,
        "deviceName": udid,
        "appPackage": APP_PKG,
        "appActivity": APP_ACT,
        "noReset": True,
        "forceAppLaunch": bool(force_launch),
        "systemPort": system_port,
        "newCommandTimeout": 360,
        "ignoreHiddenApiPolicyError": True,
        "disableWindowAnimation": True,
    }
    return webdriver.Remote(url, options=UiAutomator2Options().load_capabilities(caps))

def relanzar_app(driver):
    try:
        driver.terminate_app(APP_PKG)
    except: pass
    driver.activate_app(APP_PKG)

# =========================
# NAVEGACIÓN / SELECCIÓN
# =========================
def ir_a_chats(driver):
    # Accesibilidad
    for acc in ("Chats", "CHATS", "Conversaciones", "Conversas"):
        try:
            driver.find_element(AppiumBy.ACCESSIBILITY_ID, acc).click()
            time.sleep(0.4)
            return
        except: pass
    # Texto visible
    for xp in (
        "//android.widget.TextView[@text='Chats']",
        "//android.widget.TextView[@text='CHATS']",
        "//android.widget.TextView[contains(@text,'Chat')]",
        "//android.widget.TextView[contains(@text,'Convers')]",
    ):
        els = driver.find_elements(AppiumBy.XPATH, xp)
        if els:
            els[0].click()
            time.sleep(0.4)
            return

def abrir_chat_con(driver, contacto: str) -> bool:
    ir_a_chats(driver)

    # 1) Lista reciente
    try:
        filas = []
        for rid in ROW_IDS:
            filas = driver.find_elements(AppiumBy.ID, rid)
            if filas: break

        for fila in filas:
            try:
                header = fila.find_element(AppiumBy.ID, ROW_HEADER_ID)
                tvs = header.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView")
                nombre = (tvs[0].text or "").strip() if tvs else ""
                if contacto.lower() in nombre.lower():
                    fila.click()
                    esperar(driver, EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/entry")), 8)
                    return True
            except: continue
    except: pass

    # 2) Buscador (tu my_search_bar abre un EditText)
    try:
        driver.find_element(AppiumBy.ID, SEARCH_BAR_ID).click()
        box = esperar(driver, EC.presence_of_element_located((AppiumBy.CLASS_NAME, "android.widget.EditText")), 8)
        box.clear(); box.send_keys(contacto)
        time.sleep(1.0)
        resultados = []
        for rid in SEARCH_RESULT_ROW_IDS:
            resultados = driver.find_elements(AppiumBy.ID, rid)
            if resultados: break
        if resultados:
            resultados[0].click()
            esperar(driver, EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/entry")), 8)
            return True
    except: pass

    return False

# =========================
# LLAMADA / ESTADOS
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
    except: pass
    try:
        sub = driver.find_element(AppiumBy.ID, CALL_SUBTITLE_ID)
        return stable_text(sub)
    except:
        return ""

def tocar_boton_llamar(driver):
    # Accesibilidad directa ("Llamada")
    clicked = False
    for acc in VOICE_CALL_ACCS:
        try:
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((AppiumBy.ACCESSIBILITY_ID, acc))
            ).click()
            clicked = True
            break
        except: pass
    if not clicked:
        # Reserva: content-desc parcial
        try:
            el = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((
                AppiumBy.XPATH, "//*[contains(@content-desc,'Llam')] | //*[@content-desc[contains(.,'Call')]]"
            )))
            el.click()
            clicked = True
        except:
            pass
    if not clicked:
        raise Exception("NoVoiceCallButton")

    # Confirmación (si aparece)
    try:
        WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((AppiumBy.ID, "android:id/button1"))
        ).click()
    except:
        pass

def colgar_seguro(driver, wait_s=5):
    try:
        card = WebDriverWait(driver, wait_s).until(
            EC.presence_of_element_located((AppiumBy.ID, CALL_CONTROLS_CARD_ID))
        )
        card.find_element(AppiumBy.ID, END_CALL_BTN_ID).click()
        return
    except: pass
    try:
        WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((AppiumBy.ID, END_CALL_BTN_ID))
        ).click()
        return
    except: pass
    try:
        driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Abandonar la llamada").click()
    except:
        pass

# =========================
# WATCHERS
# =========================
def watcher_setup_A(driver_a, q: Queue, stop_evt: threading.Event):
    """Empuja 'setup' cuando texto contiene kw positivos; 'connected' cuando mm:ss."""
    ultimo = ""
    while not stop_evt.is_set():
        try:
            txt = find_subtitle_text(driver_a)
            if txt and txt != ultimo:
                ultimo = txt
            for kw in SUBTITLE_POSITIVES:
                if kw in (txt or ""):
                    q.put({"type":"setup","label":kw,"t":time.monotonic()})
                    return
            if _CONNECTED_RE.match(txt or ""):
                q.put({"type":"connected","label":"connected","t":time.monotonic()})
                return
        except: pass
        time.sleep(0.05)

def incoming_seen_on_b(driver_b) -> bool:
    CANDS = [
        (AppiumBy.ID, B_CALL_ROOT_ID),
        (AppiumBy.ID, B_ANSWER_ROOT_ID),
        (AppiumBy.ID, B_ACCEPT_CONTAINER_ID),
        (AppiumBy.ID, B_ACCEPT_SWIPE_HINT_ID),
        (AppiumBy.ID, B_ACCEPT_BUTTON_ID),
    ]
    for by, loc in CANDS:
        try:
            if driver_b.find_elements(by, loc):
                return True
        except: pass
    return False

def watcher_incoming_B(driver_b, q: Queue, stop_evt: threading.Event):
    while not stop_evt.is_set():
        try:
            if incoming_seen_on_b(driver_b):
                q.put({"type":"incoming_b","label":"fullscreen","t":time.monotonic()})
                return
        except: pass
        time.sleep(0.1)

# =========================
# MEDICIÓN ORQUESTADA
# =========================
def medir_cst_csfr_cdr(driver_a, driver_b, contacto,
                       cst_timeout=CST_TIMEOUT_S,
                       csfr_timeout=CSFR_TIMEOUT_S,
                       hold_s=CDR_HOLD_S,
                       drop_grace=DROP_GRACE_S):

    network = obtener_red_real(driver_a)
    lat, lon = obtener_gps(driver_a)
    t0_dt = datetime.now()

    # Abrir chat
    if not abrir_chat_con(driver_a, contacto):
        now_dt = datetime.now()
        for kpi, fail in (("CST","ChatNotFound"), ("CSFR","ChatNotFound"), ("CDR","ChatNotFound")):
            csv_write(kpi, contacto, t0_dt, now_dt, "Failed", fail, network=network, lat=lat, lon=lon)
        return

    # Llamar
    try:
        tocar_boton_llamar(driver_a)
    except Exception as e:
        now_dt = datetime.now()
        for kpi in ("CST","CSFR","CDR"):
            csv_write(kpi, contacto, t0_dt, now_dt, "Failed", f"NoCallBtn:{e}", network=network, lat=lat, lon=lon)
        return

    call_press_t = time.monotonic()

    # Lanzar watchers
    q = Queue()
    stop_evt = threading.Event()
    th_a = threading.Thread(target=watcher_setup_A, args=(driver_a, q, stop_evt), daemon=True)
    th_a.start()
    th_b = threading.Thread(target=watcher_incoming_B, args=(driver_b, q, stop_evt), daemon=True)
    th_b.start()

    cst_done = False; cst_t = None; cst_trigger = None
    connected_t = None
    csfr_done = False; csfr_src = None

    deadline_cst  = call_press_t + float(cst_timeout)
    deadline_csfr = call_press_t + float(csfr_timeout)

    # Ventana conjunta para CST/CSFR
    while not detener and time.monotonic() < deadline_csfr:
        # recoge eventos
        try:
            ev = q.get(timeout= min(0.2, max(0.0, deadline_csfr - time.monotonic())))
        except Empty:
            ev = None

        if ev:
            if ev["type"] == "setup" and not cst_done:
                cst_done = True; cst_t = ev["t"]; cst_trigger = ev["label"]
            elif ev["type"] == "connected":
                connected_t = ev["t"]
            elif ev["type"] == "incoming_b":
                csfr_done = True; csfr_src = ev["label"]
                # no rompas aún: permite también que CST llegue si no llegó
        # Fallback para CST si vence su ventana y ya hay mm:ss
        if (not cst_done) and (time.monotonic() >= deadline_cst) and connected_t:
            cst_done = True; cst_t = connected_t; cst_trigger = "connected"

        # Si ya tenemos ambas señales, podemos salir
        if csfr_done and cst_done:
            break

    # Cierra watchers
    stop_evt.set()
    th_a.join(timeout=0.2)
    th_b.join(timeout=0.2)

    now_dt = datetime.now()

    # ===== CSV: CST =====
    if cst_done and cst_t is not None:
        cst_val = max(0.0, cst_t - call_press_t)
        csv_write("CST", contacto, t0_dt, now_dt, "Successful", "",
                  f"setup_s={cst_val:.2f};trigger=A:{cst_trigger}",
                  network=network, lat=lat, lon=lon)
    else:
        causa = "NoSetupLabel" if network != "Disconnected" else "NoService"
        csv_write("CST", contacto, t0_dt, now_dt, "Failed", causa, "",
                  network=network, lat=lat, lon=lon)

    # ===== CSV: CSFR (requiere B) =====
    if csfr_done:
        csv_write("CSFR", contacto, t0_dt, now_dt, "Successful", "",
                  f"incoming_on_B:{csfr_src}", network=network, lat=lat, lon=lon)
    else:
        csv_write("CSFR", contacto, t0_dt, now_dt, "Failed", "NoIncomingOnB", "",
                  network=network, lat=lat, lon=lon)

    # ===== CDR =====
    # Necesitamos "connected" (mm:ss) para empezar a sostener. Si aún no hay, espera un poco más (hasta 10 s).
    if not connected_t:
        extra_wait_deadline = time.monotonic() + 10.0
        while time.monotonic() < extra_wait_deadline and not detener:
            txt = find_subtitle_text(driver_a)
            if _CONNECTED_RE.match(txt or ""):
                connected_t = time.monotonic()
                break
            time.sleep(0.2)

    if not connected_t:
        csv_write("CDR", contacto, t0_dt, datetime.now(), "Failed", "NotConnected", "",
                  network=network, lat=lat, lon=lon)
        colgar_seguro(driver_a)
        return

    # Sostener hold_s segundos: si la UI de llamada desaparece > drop_grace => Dropped
    hold_deadline = time.monotonic() + float(hold_s)
    missing_since = None
    dropped = False

    while time.monotonic() < hold_deadline and not detener:
        # Consideramos UI viva si el subtítulo existe y suele mostrar algo (mejor si mm:ss)
        alive = False
        try:
            txt = find_subtitle_text(driver_a)
            if txt:  # aceptamos cualquier subtítulo presente; idealmente mm:ss
                alive = True
        except:
            alive = False

        if alive:
            missing_since = None
        else:
            if missing_since is None:
                missing_since = time.monotonic()
            elif (time.monotonic() - missing_since) >= float(drop_grace):
                dropped = True
                break

        time.sleep(0.25)

    end_dt = datetime.now()

    if dropped:
        csv_write("CDR", contacto, t0_dt, end_dt, "Failed", "Dropped",
                  f"held_s={max(0, int(hold_s - (hold_deadline - time.monotonic())))}",
                  network=network, lat=lat, lon=lon)
    else:
        csv_write("CDR", contacto, t0_dt, end_dt, "Successful", "",
                  f"held_s={int(hold_s)}", network=network, lat=lat, lon=lon)

    colgar_seguro(driver_a)

# =========================
# MAIN
# =========================
def main():
    csv_init()
    driver_a = setup_driver(APPIUM_URL_A, UDID_A, SYSTEM_PORT_A, force_launch=True)
    driver_b = setup_driver(APPIUM_URL_B, UDID_B, SYSTEM_PORT_B, force_launch=False)
    try:
        medir_cst_csfr_cdr(driver_a, driver_b, CONTACTO,
                           cst_timeout=CST_TIMEOUT_S,
                           csfr_timeout=CSFR_TIMEOUT_S,
                           hold_s=CDR_HOLD_S,
                           drop_grace=DROP_GRACE_S)
    finally:
        try: driver_a.quit()
        except: pass
        try: driver_b.quit()
        except: pass

if __name__ == "__main__":
    main()
