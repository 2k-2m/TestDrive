# -*- coding: utf-8 -*-
import os, csv, time, signal, subprocess, re, threading
from queue import Queue, Empty
from datetime import datetime

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ========= CONFIG RÁPIDA =========
UDID = "6NUDU18529000033"                 # << R58M795NHZF Instagram
APPIUM_URL = "http://127.0.0.1:4723"
APP_PKG = "com.whatsapp"
APP_ACT = "com.whatsapp.HomeActivity"
SYSTEM_PORT = 8200                   # distinto por dispositivo
TIMEOUT_UI = 10

# CSV
timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
CSV_PATH = f"./WhatsApp_Voice_{timestamp}.csv"

# ========= ESTADO GLOBAL =========
detener = False
def manejar_senal(sig, frame):
    global detener
    print("\n[INFO] Señal recibida, deteniendo con gracia...")
    detener = True
signal.signal(signal.SIGINT, manejar_senal)
signal.signal(signal.SIGTERM, manejar_senal)

# ========= CSV =========
CSV_HEADER = [
    "App","Network","KPI","Contact",
    "Latitude","Longitude",
    "Start","End","Result","Failure","Extra"
]

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

# ========= UTILIDADES ANDROID =========
def obtener_red_real(driver):
    try:
        out = driver.execute_script("mobile: shell", {
            "command":"dumpsys","args":["connectivity"],"includeStderr":True,"timeout":5000
        })["stdout"]
        if "state: CONNECTED" in out and "VALIDATED" in out:
            if "type: WIFI" in out:    return "WiFi"
            if "type: MOBILE" in out:  return "Mobile"
    except:
        pass
    return "Disconnected"   # patrón de tus scripts

def obtener_gps(driver):
    try:
        loc = driver.location
        return str(loc.get("latitude","")), str(loc.get("longitude",""))
    except:
        return "", ""

def esperar(drv, cond, t=TIMEOUT_UI):
    return WebDriverWait(drv, t).until(cond)

# ========= DRIVER / APP =========
def setup_driver():
    caps = {
        "platformName":"Android",
        "deviceName": UDID,
        "udid": UDID,
        "automationName":"UiAutomator2",
        "appPackage": APP_PKG,
        "appActivity": APP_ACT,
        "noReset": True,
        "forceAppLaunch": True,
        "systemPort": SYSTEM_PORT,
        "newCommandTimeout": 360
    }
    return webdriver.Remote(APPIUM_URL, options=UiAutomator2Options().load_capabilities(caps))

def relanzar_app(driver):
    driver.terminate_app(APP_PKG)
    driver.activate_app(APP_PKG)

# ========= NAVEGACIÓN WHATSAPP =========
def abrir_chat_con(driver, contacto):
    """
    Estrategia simple: buscar en lista reciente de chats.
    Si no aparece, usar lupa y buscar.
    """
    try:
        # 1) Intentar por lista de chats (recientes)
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
        # 2) Plan B: lupa
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

# ========= SELECTORES DE LLAMADA =========
SEL_CALL_HEADER    = (AppiumBy.ID, "com.whatsapp:id/call_screen_header_view")
SEL_CALL_SUBTITLE  = (AppiumBy.ID, "com.whatsapp:id/subtitle")

# ====== Palabras/regex de estados ======
_CONNECTED_RE     = re.compile(r"^\d{1,2}:\d{2}$")  # 0:00, 12:34, etc.

# ====== NUEVOS SELECTORES/CONSTS PARA MEDICIÓN UNIFICADA ======
SUBTITLE_ID = "com.whatsapp:id/subtitle"
CALL_CONTROLS_CARD_ID = "com.whatsapp:id/call_controls_card"
END_CALL_BUTTON_ID = "com.whatsapp:id/end_call_button"

# Para CST (estrictos). Si validas que 'llamando' coincide con ring real en tu build, añádelo.
SUBTITLE_POSITIVES = ("cifrado", "llamando", "calling", "sonando", "ringing")

# Si True, si no se vio ningún label de setup pero sí aparece mm:ss,
# CST se calcula con ese instante (evita el caso CST=Failed y CSFR=Success)
ALLOW_CONNECTED_AS_CST_FALLBACK = True



# ========= HELPERS NUEVOS =========
def now_mono() -> float:
    """Reloj monotónico (no se ve afectado por cambios de hora del SO)."""
    return time.monotonic()

def stable_text(element, min_ms: int = 250) -> str:
    """Lee texto estabilizado para evitar flicker (cambios rápidos)."""
    t0 = now_mono()
    last = element.text or ""
    while (now_mono() - t0) * 1000 < min_ms:
        cur = element.text or ""
        if cur != last:
            t0 = now_mono()
            last = cur
        time.sleep(0.03)
    return (last or "").strip().lower().replace("…", "...")

def find_subtitle_text(driver) -> str:
    """Lee el subtitle del header; si falla, usa el id directo."""
    try:
        header = driver.find_element(*SEL_CALL_HEADER)
        sub = header.find_element(*SEL_CALL_SUBTITLE)
        return stable_text(sub)
    except:
        pass
    try:
        el = driver.find_element(AppiumBy.ID, SUBTITLE_ID)
        return stable_text(el)
    except:
        return ""

def matches_positive_subtitle(t: str):
    """Devuelve la palabra clave que indica ring (si aplica)."""
    for kw in SUBTITLE_POSITIVES:
        if kw in t:
            return kw
    return None

# ========= BOTÓN LLAMAR / COLGAR =========
def _tocar_boton_llamar(driver):
    """Presiona el botón 'Llamada' y confirma si aparece el popup."""
    try:
        WebDriverWait(driver, 6).until(
            EC.element_to_be_clickable((AppiumBy.ACCESSIBILITY_ID, "Llamada"))
        ).click()
        print("Botón 'Llamada' presionado correctamente.")

        try:
            confirmar = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((AppiumBy.ID, "android:id/button1"))
            )
            confirmar.click()
            print("[INFO] Confirmación 'Llamar' presionada.")
        except:
            pass
    except Exception as e:
        print(f"[ERROR] No se pudo presionar 'Llamada': {e}")
        raise

def _colgar_seguro(driver, wait_s=5):
    """
    Colgar usando el selector correcto: end_call_button dentro de call_controls_card.
    Con fallbacks por ID directo y accesibilidad.
    """
    # 1) Dentro de la card (tu hallazgo)
    try:
        card = WebDriverWait(driver, wait_s).until(
            EC.presence_of_element_located((AppiumBy.ID, CALL_CONTROLS_CARD_ID))
        )
        card.find_element(AppiumBy.ID, END_CALL_BUTTON_ID).click()
        print("[INFO] Llamada colgada (card/end_call_button).")
        return
    except Exception:
        pass
    # 2) Fallback: ID directo
    try:
        WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((AppiumBy.ID, END_CALL_BUTTON_ID))
        ).click()
        print("[INFO] Llamada colgada (end_call_button directo).")
        return
    except Exception:
        pass
    # 3) Fallback: accesibilidad
    try:
        driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Abandonar la llamada").click()
        print("[INFO] Llamada colgada (fallback accesibilidad).")
    except:
        print("[WARN] No se pudo colgar (no visible).")

# ========= WATCHER (A) PARA SETUP =========
def watcher_setup_A(driver, q: Queue, stop_evt: threading.Event):

    ultimo = ""
    while not stop_evt.is_set():
        try:
            txt = find_subtitle_text(driver)
            if txt and txt != ultimo:
                # print(f"[CALL-STATE] {txt}")  # opcional
                ultimo = txt

            # ---- SETUP: cifrado / llamando / calling / sonando / ringing ----
            for kw in SUBTITLE_POSITIVES:
                if kw in (txt or ""):
                    q.put({"label": kw, "type": "setup", "t": time.monotonic()})
                    return

            # ---- CONNECTED: mm:ss ----
            if _CONNECTED_RE.match(txt or ""):
                q.put({"label": "connected", "type": "connected", "t": time.monotonic()})
                return
        except:
            pass
        time.sleep(0.05)


# ========= MEDICIÓN UNIFICADA: CST + CSFR =========
def medir_cst_csfr(driver, contacto, timeout_setup=20):
    """
    - CST: tiempo hasta PRIMER 'setup' (cifrado/llamando/sonando...). Si no hubo label,
      opcionalmente usa 'connected' (mm:ss) como fallback si ALLOW_CONNECTED_AS_CST_FALLBACK=True.
    - CSFR: Success si hubo 'setup' o 'connected' dentro del timeout.
    Escribe DOS filas en el CSV (CST y CSFR).
    """
    network = obtener_red_real(driver)
    lat, lon = obtener_gps(driver)
    t0_dt = datetime.now()

    if not abrir_chat_con(driver, contacto):
        now_dt = datetime.now()
        csv_write("CST",  contacto, t0_dt, now_dt, "Failed", "ChatNotFound",
                  network=network, lat=lat, lon=lon)
        csv_write("CSFR", contacto, t0_dt, now_dt, "Failed", "ChatNotFound",
                  network=network, lat=lat, lon=lon)
        return

    # Inicia llamada
    try:
        _tocar_boton_llamar(driver)
    except Exception as e:
        now_dt = datetime.now()
        err = f"NoCallBtn:{e}"
        csv_write("CST",  contacto, t0_dt, now_dt, "Failed", err, network=network, lat=lat, lon=lon)
        csv_write("CSFR", contacto, t0_dt, now_dt, "Failed", err, network=network, lat=lat, lon=lon)
        return

    t_start = time.monotonic()

    # Watcher
    q = Queue()
    stop_evt = threading.Event()
    th = threading.Thread(target=watcher_setup_A, args=(driver, q, stop_evt), daemon=True)
    th.start()

    # Espera evento o timeout
    hit = None
    deadline = t_start + float(timeout_setup)
    while time.monotonic() < deadline:
        try:
            hit = q.get(timeout=0.05)
            break
        except Empty:
            pass

    stop_evt.set()
    th.join(timeout=0.2)

    end_dt = datetime.now()

    if hit:
        if hit["type"] == "setup":
            cst = max(0.0, hit["t"] - t_start)
            csv_write("CST",  contacto, t0_dt, end_dt, "Successful", "",
                      f"setup_s={cst:.2f};trigger=A:{hit['label']}",
                      network=network, lat=lat, lon=lon)
            csv_write("CSFR", contacto, t0_dt, end_dt, "Successful", "",
                      "setup_ok", network=network, lat=lat, lon=lon)

        elif hit["type"] == "connected":
            # Fallback configurable: usa el instante de 'connected' para CST si se permite
            if ALLOW_CONNECTED_AS_CST_FALLBACK:
                cst = max(0.0, hit["t"] - t_start)
                csv_write("CST",  contacto, t0_dt, end_dt, "Successful", "",
                          f"setup_s={cst:.2f};trigger=A:connected",
                          network=network, lat=lat, lon=lon)
            else:
                csv_write("CST",  contacto, t0_dt, end_dt, "Failed", "NoSetupLabel",
                          "connected_first", network=network, lat=lat, lon=lon)

            csv_write("CSFR", contacto, t0_dt, end_dt, "Successful", "",
                      "connected_ok", network=network, lat=lat, lon=lon)

    else:
        causa = "NoService" if network == "Disconnected" else "NoRingback"
        csv_write("CST",  contacto, t0_dt, end_dt, "Failed", causa, "",
                  network=network, lat=lat, lon=lon)
        csv_write("CSFR", contacto, t0_dt, end_dt, "Failed", causa, "",
                  network=network, lat=lat, lon=lon)

    _colgar_seguro(driver)

def sanity_chats(driver, timeout=12):
    try:
        # Nota: EC.any_of puede no estar en todas las versiones; si falla, ignora.
        esperar(driver, EC.any_of(
            EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "Chats")),
            EC.presence_of_element_located((AppiumBy.XPATH, "//android.widget.TextView[@text='Chats']"))
        ), timeout)
    except Exception:
        print("[WARN] 'Chats' no visible, continuamos...")

# ========= MAIN LOOP =========
def main():
    csv_init()
    driver = setup_driver()
    try:
        sanity_chats(driver)
        contacto = "vast_wB"
        if detener:
            return
        medir_cst_csfr(driver, contacto, timeout_setup=20)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
