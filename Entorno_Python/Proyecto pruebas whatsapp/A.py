import os, csv, time, re, threading, signal
from datetime import datetime
from queue import Queue, Empty
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import unicodedata

# ========= CONFIG DISPOSITIVO A =========
UDID_A = "6NUDU18529000033"               # serial del teléfono A
APPIUM_URL_A = "http://127.0.0.1:4723"    # Appium de A
SYSTEM_PORT_A = 8206

# ========= OBSERVADOR B (solo lectura para CSFR) =========
# No contesta ni desliza. Solo mira la UI para confirmar "entró" la llamada.
UDID_B = "YLEDU17215000182"                    #serial del teléfono B
APPIUM_URL_B = "http://127.0.0.1:4726"    # Appium de B 
SYSTEM_PORT_B_OBS = 8212                

APP_PKG = "com.whatsapp"
APP_ACT = "com.whatsapp.HomeActivity"

# ========= CSV =========
timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
CSV_PATH = f"./WhatsApp_CST_CSFR_{timestamp}.csv"
CSV_HEADER = [
    "App","Network","KPI","Contact",
    "Latitude","Longitude",
    "Start","End","Result","Failure","Extra"
]

# ========= FLAGS =========
REQUIRE_B_FOR_CSFR = True                # CSFR exige ver incoming en B
ALLOW_CONNECTED_AS_CST_FALLBACK = True   # si no hay label de setup pero aparece mm:ss

# ========= SELECTORES / ESTADOS EN A =========
SEL_CALL_HEADER    = (AppiumBy.ID, "com.whatsapp:id/call_screen_header_view")
SEL_CALL_SUBTITLE  = (AppiumBy.ID, "com.whatsapp:id/subtitle")
CALL_CONTROLS_CARD = "com.whatsapp:id/call_controls_card"
END_CALL_BUTTON    = "com.whatsapp:id/end_call_button"

_CONNECTED_RE      = re.compile(r"^\d{1,2}:\d{2}$")  # 0:00, 12:34
SUBTITLE_POSITIVES = (
    "cifrado", "llamando", "calling", "sonando", "ringing",
    "marcando", "conectando"  
)

# ========= SELECTORES EN B (tus IDs exactos) =========
B_INCOMING_LOCATORS = [
    (AppiumBy.ID, "com.whatsapp:id/accept_incoming_call_view"),       # botón aceptar (content-desc)
    (AppiumBy.ID, "com.whatsapp:id/accept_call_swipe_up_hint_view"),  # contenedor/área para deslizar
    (AppiumBy.ID, "com.whatsapp:id/action_bar_root"),                 # raíz de la pantalla fullscreen entrante
    (AppiumBy.ACCESSIBILITY_ID, "Botón para aceptar la llamada. Toca dos veces para aceptar."),
]
# Fallback corto (notificación)
B_NOTIFICATION_HINTS = [
    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Llamada entrante")'),
    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().descriptionContains("Llamada entrante")'),
]

SEL_CHAT_ENTRY = (AppiumBy.ID, "com.whatsapp:id/entry")

# ========= ESTADO GLOBAL =========
detener = False
def manejar_senal(sig, frame):
    global detener
    print("\n[INFO] Señal recibida, deteniendo con gracia...")
    detener = True
signal.signal(signal.SIGINT, manejar_senal)
signal.signal(signal.SIGTERM, manejar_senal)

# ========= CSV =========
def csv_init(path=CSV_PATH):
    if not os.path.exists(path) or os.path.getsize(path)==0:
        with open(path,"w",newline="",encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADER)

def csv_write(kpi, contact, start_dt, end_dt, result, failure="", extra="",
              network="", lat="", lon="", app="WhatsApp"):
    with open(CSV_PATH,"a",newline="",encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            app, network, kpi, contact,
            lat, lon,
            start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            result, failure, extra
        ])

# ========= ANDROID HELPERS =========
def obtener_red_real(driver):
    try:
        out = driver.execute_script("mobile: shell", {
            "command":"dumpsys","args":["connectivity"],"includeStderr":True,"timeout":7000
        })["stdout"]
        if "state: CONNECTED" in out and "VALIDATED" in out:
            if "type: WIFI" in out:    return "WiFi"
            if "type: MOBILE" in out:  return "Mobile"
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

# ========= DRIVERS =========
def setup_driver_a():
    caps = {
        "platformName": "Android",
        "automationName": "UiAutomator2",
        "udid": UDID_A,
        "deviceName": UDID_A,

        "appPackage": APP_PKG,
        "appActivity": APP_ACT,

        "noReset": True,
        "forceAppLaunch": True,
        "systemPort": SYSTEM_PORT_A,
        "newCommandTimeout": 360,

        "ignoreHiddenApiPolicyError": True,
        "disableWindowAnimation": True,
    }
    return webdriver.Remote(APPIUM_URL_A, options=UiAutomator2Options().load_capabilities(caps))

def setup_driver_b_observer():
    """Conecta a B (solo lectura) para confirmar 'incoming'. No interactúa."""
    caps = {
        "platformName": "Android",
        "automationName": "UiAutomator2",
        "udid": UDID_B,
        "deviceName": UDID_B,

        "noReset": True,
        "forceAppLaunch": False,     # no cambiar de app en B
        "systemPort": SYSTEM_PORT_B_OBS,
        "newCommandTimeout": 360,

        "ignoreHiddenApiPolicyError": True,
        "disableWindowAnimation": True,
    }
    return webdriver.Remote(APPIUM_URL_B, options=UiAutomator2Options().load_capabilities(caps))

def relanzar_app(driver):
    driver.terminate_app(APP_PKG)
    driver.activate_app(APP_PKG)

# ========= NAVEGACIÓN EN A =========
def abrir_chat_con(driver, contacto):
    """Recientes -> si no, lupa."""
    try:
        candidatos = driver.find_elements(AppiumBy.ID, "com.whatsapp:id/contact_row_container")
        for c in candidatos:
            try:
                nombre = c.find_element(AppiumBy.ID, "com.whatsapp:id/conversations_row_contact_name").text
                if contacto.lower() in (nombre or "").lower():
                    c.click()
                    esperar(driver, EC.presence_of_element_located((AppiumBy.ID,"com.whatsapp:id/entry")), 8)
                    return True
            except:
                continue
        # Lupa
        try:
            driver.find_element(AppiumBy.ACCESSIBILITY_ID,"Buscar").click()
            box = esperar(driver, EC.presence_of_element_located((AppiumBy.ID,"com.whatsapp:id/search_input")), 8)
            box.send_keys(contacto)
            time.sleep(1.0)
            resultado = driver.find_elements(AppiumBy.ID, "com.whatsapp:id/contactpicker_row_name")
            if resultado:
                resultado[0].click()
                esperar(driver, EC.presence_of_element_located((AppiumBy.ID,"com.whatsapp:id/entry")), 8)
                return True
        except:
            pass
    except:
        pass
    return False

# ========= TEXTO/ESTADOS EN A =========
def now_mono():
    return time.monotonic()

def stable_text(element, min_ms: int = 250) -> str:
    t0 = now_mono()
    last = element.text or ""
    while (now_mono() - t0) * 1000 < min_ms:
        cur = element.text or ""
        if cur != last:
            t0 = now_mono()
            last = cur
        time.sleep(0.03)
    return (last or "").strip().lower().replace("…", "...")

def _normalize_text(s: str) -> str:
    # Normaliza Unicode (quita rarezas), baja a minúsculas 'real' y limpia
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("…", "...")  # WhatsApp suele usar U+2026
    return s.strip().casefold()  # casefold > lower para comparaciones robustas

def find_subtitle_text(driver) -> str:
    try:
        header = driver.find_element(*SEL_CALL_HEADER)
        sub = header.find_element(*SEL_CALL_SUBTITLE)
        return stable_text(sub)
    except:
        pass
    try:
        el = driver.find_element(AppiumBy.ID, "com.whatsapp:id/subtitle")
        return stable_text(el)
    except:
        return ""

# ========= BOTONES EN A =========
def _tocar_boton_llamar(driver):
    WebDriverWait(driver, 6).until(
        EC.element_to_be_clickable((AppiumBy.ACCESSIBILITY_ID, "Llamada"))
    ).click()
    try:
        confirmar = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((AppiumBy.ID, "android:id/button1"))
        )
        confirmar.click()
    except:
        pass

def _colgar_seguro(driver, wait_s=5):
    try:
        card = WebDriverWait(driver, wait_s).until(
            EC.presence_of_element_located((AppiumBy.ID, CALL_CONTROLS_CARD))
        )
        card.find_element(AppiumBy.ID, END_CALL_BUTTON).click()
        return
    except:
        pass
    try:
        WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((AppiumBy.ID, END_CALL_BUTTON))
        ).click()
        return
    except:
        pass
    try:
        driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Abandonar la llamada").click()
    except:
        pass

# ========= WATCHERS =========
def watcher_setup_A(driver_a, q: Queue, stop_evt: threading.Event):
    """
    Empuja el PRIMER evento en A:
      - {'type':'setup','label':kw,'t':...} si ve SUBTITLE_POSITIVES (cifrado/llamando/sonando...)
      - {'type':'connected','label':'connected','t':...} si ve mm:ss
    """
    ultimo = ""
    while not stop_evt.is_set():
        try:
            txt = find_subtitle_text(driver_a)
            if txt and txt != ultimo:
                ultimo = txt
            for kw in SUBTITLE_POSITIVES:
                if kw in (txt or ""):
                    q.put({"type":"setup","label":kw,"t":now_mono()})
                    return
            if _CONNECTED_RE.match(txt or ""):
                q.put({"type":"connected","label":"connected","t":now_mono()})
                return
        except:
            pass
        time.sleep(0.05)

def incoming_seen_on_b(driver_b) -> bool:
    """True si cualquiera de los locators en B está presente (pantalla completa)."""
    for by, loc in B_INCOMING_LOCATORS:
        try:
            if driver_b.find_elements(by, loc):
                return True
        except:
            pass
    return False

def incoming_via_notification_on_b(driver_b) -> bool:
    """Fallback muy corto: busca 'Llamada entrante' en la bandeja."""
    try:
        driver_b.open_notifications()
        time.sleep(0.5)
        for by, loc in B_NOTIFICATION_HINTS:
            try:
                if driver_b.find_elements(by, loc):
                    # cerrar bandeja y confirmar
                    try: driver_b.back()
                    except: pass
                    return True
            except:
                pass
    except:
        pass
    try:
        driver_b.back()  # cierra bandeja si quedó abierta
    except:
        pass
    return False

def watcher_incoming_B(driver_b, q: Queue, stop_evt: threading.Event):
    """
    Confirma que 'entró' la llamada a B:
      - Detecta pantalla completa de entrante (tus IDs)
      - Si no, intenta un ping corto en la notificación
    """
    while not stop_evt.is_set():
        try:
            if incoming_seen_on_b(driver_b):
                q.put({"type":"incoming_b","label":"fullscreen","t":now_mono()})
                return
            # intento breve de notificación (no bloqueante)
            if incoming_via_notification_on_b(driver_b):
                q.put({"type":"incoming_b","label":"notification","t":now_mono()})
                return
        except:
            pass
        time.sleep(0.1)

def is_in_chat_view(driver) -> bool:
    """Devuelve True si estamos dentro de una conversación (se ve la caja de texto)."""
    try:
        return bool(driver.find_elements(*SEL_CHAT_ENTRY))
    except:
        return False

def wait_call_ui_visible(driver, timeout=8) -> bool:
    CALL_CONTROLS_CARD = "com.whatsapp:id/call_controls_card"
    END_CALL_BUTTON    = "com.whatsapp:id/end_call_button"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if driver.find_elements(*SEL_CALL_HEADER):
                return True
        except: pass
        try:
            if driver.find_elements(AppiumBy.ID, END_CALL_BUTTON):
                return True
        except: pass
        try:
            if driver.find_elements(AppiumBy.ID, CALL_CONTROLS_CARD):
                return True
        except: pass
        time.sleep(0.1)
    return False

# ========= MEDICIÓN: CST + CSFR (con confirmación en B) =========
def medir_cst_csfr_con_b(
    driver_a,
    contacto: str,
    driver_b=None,
    cst_timeout: float = 20.0,
    csfr_timeout: float = 20.0
):
    """
    - CST: primer instante en A con SUBTITLE_POSITIVES; si no y ALLOW_CONNECTED_AS_CST_FALLBACK, usa mm:ss.
    - CSFR: Success SOLO si B reporta 'incoming' (fullscreen o notificación) antes de csfr_timeout.
    """
    network = obtener_red_real(driver_a); lat, lon = obtener_gps(driver_a)
    t0_dt = datetime.now()

    if not (abrir_chat_con(driver_a, contacto) or is_in_chat_view(driver_a)):
        now_dt = datetime.now()
        csv_write("CST",  contacto, t0_dt, now_dt, "Failed", "ChatNotFound", network=network, lat=lat, lon=lon)
        csv_write("CSFR", contacto, t0_dt, now_dt, "Failed", "ChatNotFound", network=network, lat=lat, lon=lon)
        return

    # Llamar
    try:
        _tocar_boton_llamar(driver_a)
    except Exception as e:
        now_dt = datetime.now()
        err = f"NoCallBtn:{e}"
        csv_write("CST",  contacto, t0_dt, now_dt, "Failed", err, network=network, lat=lat, lon=lon)
        csv_write("CSFR", contacto, t0_dt, now_dt, "Failed", err, network=network, lat=lat, lon=lon)
        return

    # >>> NUEVO: esperar que aparezca la UI de llamada (header/botón/controles)
    wait_call_ui_visible(driver_a, timeout=8)

    t_start = now_mono()

    # Watchers
    q = Queue(); stop_evt = threading.Event()
    th_a = threading.Thread(target=watcher_setup_A, args=(driver_a, q, stop_evt), daemon=True)
    th_a.start()

    th_b = None
    if driver_b is not None:
        th_b = threading.Thread(target=watcher_incoming_B, args=(driver_b, q, stop_evt), daemon=True)
        th_b.start()

    cst_done = False; cst_t = None; cst_trigger = None
    connected_t = None
    csfr_done = False; csfr_src = None

    deadline_cst  = t_start + float(cst_timeout)
    deadline_csfr = t_start + float(csfr_timeout)

    while not detener and now_mono() < deadline_csfr:
        # poll pequeño
        poll = min(0.2, max(0.0, deadline_csfr - now_mono()))
        ev = None
        try:
            ev = q.get(timeout=poll)
        except Empty:
            ev = None

        if ev:
            if ev["type"] == "setup" and not cst_done:
                cst_done = True; cst_t = ev["t"]; cst_trigger = ev["label"]
            elif ev["type"] == "connected":
                connected_t = ev["t"]
            elif ev["type"] == "incoming_b":
                # >>> CAMBIO: marcar CSFR pero NO cortar aún
                csfr_done = True
                csfr_src = ev["label"]
                # (seguimos para que CST se resuelva o venza su ventana)

        # Fallback para CST cuando vence su ventana
        if (not cst_done) and (now_mono() >= deadline_cst) and connected_t and ALLOW_CONNECTED_AS_CST_FALLBACK:
            cst_done = True; cst_t = connected_t; cst_trigger = "connected"

        # >>> NUEVO criterio de salida:
        # Salir cuando CSFR ya está decidido y CST ya se resolvió,
        # o cuando venció la ventana de CST (para que el fallback mm:ss se aplique si corresponde).
        if csfr_done and (cst_done or now_mono() >= deadline_cst):
            break

    # Cerrar watchers
    stop_evt.set()
    th_a.join(timeout=0.2)
    if th_b: th_b.join(timeout=0.2)

    end_dt = datetime.now()

    # ===== CSV: CST =====
    if cst_done and cst_t is not None:
        cst_val = max(0.0, cst_t - t_start)
        csv_write("CST", contacto, t0_dt, end_dt, "Successful", "",
                  f"setup_s={cst_val:.2f};trigger=A:{cst_trigger}",
                  network=network, lat=lat, lon=lon)
    else:
        causa = "NoSetupLabel" if network != "Disconnected" else "NoService"
        csv_write("CST", contacto, t0_dt, end_dt, "Failed", causa, "",
                  network=network, lat=lat, lon=lon)

    # ===== CSV: CSFR =====
    if REQUIRE_B_FOR_CSFR:
        if driver_b is None:
            csv_write("CSFR", contacto, t0_dt, end_dt, "Failed", "NoBDriver", "",
                      network=network, lat=lat, lon=lon)
        else:
            if csfr_done:
                csv_write("CSFR", contacto, t0_dt, end_dt, "Successful", "",
                          f"incoming_on_B:{csfr_src}", network=network, lat=lat, lon=lon)
            else:
                csv_write("CSFR", contacto, t0_dt, end_dt, "Failed", "NoIncomingOnB", "",
                          network=network, lat=lat, lon=lon)
    else:
        # Fallback A-only (no recomendado para validación dura)
        if cst_done or connected_t:
            csv_write("CSFR", contacto, t0_dt, end_dt, "Successful", "", "setup_ok",
                      network=network, lat=lat, lon=lon)
        else:
            causa = "NoRingback" if network != "Disconnected" else "NoService"
            csv_write("CSFR", contacto, t0_dt, end_dt, "Failed", causa, "",
                      network=network, lat=lat, lon=lon)

    _colgar_seguro(driver_a)


#CDR--------------------------------


def wait_for_connected_timer(driver, timeout_s: float = 25.0):
    """Espera a ver el cronómetro mm:ss en el subtítulo. Devuelve (True, t_mono) si conecta."""
    deadline = time.monotonic() + timeout_s
    last = ""
    while time.monotonic() < deadline:
        try:
            txt = find_subtitle_text(driver)  # ya normaliza con _normalize_text
            if txt and txt != last:
                # print(f"[A-subtitle] {txt}")  # <-- descomenta si quieres ver el flujo
                last = txt
            if _CONNECTED_RE.match(txt or ""):
                return True, time.monotonic()
        except:
            pass
        time.sleep(0.1)
    return False, None


def is_call_ui_active(driver):
    """Activo si vemos mm:ss o la card de controles de llamada."""
    try:
        txt = find_subtitle_text(driver)
        if _CONNECTED_RE.match(txt or ""):
            return True
    except:
        pass
    try:
        if driver.find_elements(AppiumBy.ID, CALL_CONTROLS_CARD):
            return True
    except:
        pass
    return False


def medir_cdr(
    driver_a,
    contacto: str,
    setup_timeout: float = 25.0,
    hold_seg: float = 30.0,
    drop_grace_s: float = 2.0
):
    """
    CDR (Call Drop Rate):
      1) Asegura/abre chat con contacto.
      2) Inicia llamada y espera 'connected' (mm:ss) hasta setup_timeout.
      3) Sostiene 'hold_seg' segundos; si la UI de llamada desaparece > drop_grace_s -> DROP.
      4) CSV: KPI=CDR con 'Successful' (held_s=...) o 'Failed' (Dropped, drop_at_s=...).
    """
    network = obtener_red_real(driver_a); lat, lon = obtener_gps(driver_a)
    t0_dt = datetime.now()

    # Asegura estar en la conversación (evita falsos ChatNotFound si ya estabas adentro)
    if not (abrir_chat_con(driver_a, contacto) or is_in_chat_view(driver_a)):
        now_dt = datetime.now()
        csv_write("CDR", contacto, t0_dt, now_dt, "Failed", "ChatNotFound", "",
                  network=network, lat=lat, lon=lon)
        return

    # Botón 'Llamada'
    try:
        _tocar_boton_llamar(driver_a)
    except Exception as e:
        now_dt = datetime.now()
        csv_write("CDR", contacto, t0_dt, now_dt, "Failed", f"NoCallBtn:{e}", "",
                  network=network, lat=lat, lon=lon)
        return

    # Espera que la UI de llamada aparezca (header/botón/controles)
    wait_call_ui_visible(driver_a, timeout=8)

    # Espera conexión (mm:ss)
    connected, t_conn = wait_for_connected_timer(driver_a, timeout_s=setup_timeout)
    if not connected:
        csv_write("CDR", contacto, t0_dt, datetime.now(), "Failed", "NoConnect", "",
                  network=network, lat=lat, lon=lon)
        _colgar_seguro(driver_a)
        return

    # Ventana de “sostener” y detección de drop
    t_start_hold = time.monotonic()
    missing_since = None
    drop = False
    while (time.monotonic() - t_start_hold) < hold_seg:
        active = is_call_ui_active(driver_a)
        if active:
            missing_since = None
        else:
            if missing_since is None:
                missing_since = time.monotonic()
            if (time.monotonic() - missing_since) >= drop_grace_s:
                drop = True
                break
        time.sleep(0.25)

    end_dt = datetime.now()
    if drop:
        drop_at = time.monotonic() - t_start_hold
        csv_write("CDR", contacto, t0_dt, end_dt,
                  "Failed", "Dropped", f"drop_at_s={drop_at:.1f}",
                  network=network, lat=lat, lon=lon)
    else:
        csv_write("CDR", contacto, t0_dt, end_dt,
                  "Successful", "", f"held_s={hold_seg:.1f}",
                  network=network, lat=lat, lon=lon)

    _colgar_seguro(driver_a)
    # (opcional) volver a 'Chats' si vas a correr múltiples iteraciones:
    # ensure_on_chats(driver_a, retry=2)









# ========= MAIN =========
def main():
    csv_init()
    driver_a = setup_driver_a()
    driver_b = None
    try:
        # Creamos sesión OBSERVADORA a B (solo lectura)
        driver_b = setup_driver_b_observer()

        contacto = "vast_wB"   # <--- ajusta al nombre del chat/contacto (B)
        #medir_cst_csfr_con_b(driver_a, contacto, driver_b=driver_b, cst_timeout=20, csfr_timeout=20)

        #time.sleep(2)

        #medir_cst_csfr_con_b(driver_a, contacto, driver_b=driver_b, cst_timeout=20, csfr_timeout=20)

        #time.sleep(2)

        medir_cdr(driver_a, contacto="vast_wB", setup_timeout=25, hold_seg=30, drop_grace_s=2)

    finally:
        try:
            driver_a.quit()
        except: pass
        try:
            if driver_b: driver_b.quit()
        except: pass

if __name__ == "__main__":
    main()
