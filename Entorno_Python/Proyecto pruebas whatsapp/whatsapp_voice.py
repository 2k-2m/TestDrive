# -*- coding: utf-8 -*-
import os, csv, time, signal, subprocess, re
from datetime import datetime
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ========= CONFIG RÁPIDA =========
UDID = "R58M795NHZF"                 # << R58M795NHZF Instagram
APPIUM_URL = "http://127.0.0.1:4723"
APP_PKG = "com.whatsapp"
APP_ACT = "com.whatsapp.HomeActivity"
SYSTEM_PORT = 8200                  # distinto por dispositivo
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
    except: pass
    return "Disconnected"   # tomado del patrón de tus scripts

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
    Si no aparece, usar lupa y buscar (puedes ampliar aquí).
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
            except: continue
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
        except: pass
    except: pass
    return False

# ========= SELECTORES DE LLAMADA (ajusta a tu build/idioma) =========
# ========= SELECTORES DE LLAMADA =========
# ========= SELECTORES DE LLAMADA =========
SEL_BOTON_COLGAR = (AppiumBy.ID, "com.whatsapp:id/end_call_button")
SEL_CALL_HEADER    = (AppiumBy.ID, "com.whatsapp:id/call_screen_header_view")
SEL_CALL_SUBTITLE  = (AppiumBy.ID, "com.whatsapp:id/subtitle")

# Palabras clave que indican que ya se estableció ringback
CALLING_KEYWORDS   = ["llamando", "calling", "cifrado"]

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

def _leer_subtitulo_llamada(driver) -> str:
    """Lee el subtítulo del header de llamada."""
    try:
        header = driver.find_element(*SEL_CALL_HEADER)
        sub = header.find_element(*SEL_CALL_SUBTITLE)
        return (sub.text or "").strip().lower().replace("…", "...")
    except:
        return ""

def medir_cst(driver, contacto, timeout_ringback=20):
    """
    CST: desde presionar 'Llamar' hasta que aparece 'llamando' o 'cifrado de extremo a extremo'.
    """
    network = obtener_red_real(driver)
    lat, lon = obtener_gps(driver)
    t0_dt = datetime.now()

    if not abrir_chat_con(driver, contacto):
        csv_write("CST", contacto, t0_dt, datetime.now(),
                  "Failed", "ChatNotFound", network=network, lat=lat, lon=lon)
        return

    try:
        _tocar_boton_llamar(driver)
        t_start = time.time()

        fin = time.time() + timeout_ringback
        while time.time() < fin:
            txt = _leer_subtitulo_llamada(driver)
            if txt:
                print(f"[CALL-STATE] {txt}")
            if any(k in txt for k in CALLING_KEYWORDS):
                setup_s = f"setup_s={(time.time()-t_start):.2f}"
                csv_write("CST", contacto, t0_dt, datetime.now(),
                          "Successful", extra=setup_s,
                          network=network, lat=lat, lon=lon)
                return
            time.sleep(0.3)

        # timeout
        csv_write("CST", contacto, t0_dt, datetime.now(),
                  "Failed", "NoCalling", network=network, lat=lat, lon=lon)

    finally:
        try:
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(SEL_BOTON_COLGAR)
            ).click()
            print("[INFO] Llamada colgada.")
        except Exception as e:
            print(f"[WARN] No se pudo colgar la llamada: {e}")


# def medir_CST(driver, contacto, timeout_conexion=25):
#     """
#     Call Setup Time: Tap al botón de llamada -> estado 'en llamada'.
#     """
#     network = obtener_red_real(driver); lat, lon = obtener_gps(driver)
#     start = datetime.now()
#     try:
#         if not abrir_chat_con(driver, contacto):
#             csv_write("CST", contacto, start, datetime.now(), "Failed", "Item no found", network=network, lat=lat, lon=lon)
#             return

#         # Tap en botón de llamada (puede estar en toolbar o menú adjunto)
#         try:
#             esperar(driver, EC.element_to_be_clickable(SEL_BOTON_LLAMAR), 6).click()
#         except:
#             # Fallback: botón teléfono en la cabecera
#             driver.find_element(AppiumBy.ACCESSIBILITY_ID,"Llamar").click()

#         # Esperar estado “conectado”: UI de llamada activa (ajusta selector a tu build)
#         esperar(driver, EC.presence_of_element_located(SEL_ESTADO_EN_LLAMADA), timeout_conexion)
#         end = datetime.now()
#         csv_write("CST", contacto, start, end, "Successful", extra=f"setup_s={(end-start).total_seconds():.2f}",
#                   network=network, lat=lat, lon=lon)
#     except TimeoutException:
#         csv_write("CST", contacto, start, datetime.now(),
#                   "Failed", "Timeout", network=network, lat=lat, lon=lon)
#     except Exception as e:
#         csv_write("CST", contacto, start, datetime.now(),
#                   "Failed", str(e), network=network, lat=lat, lon=lon)

# ====== Palabras clave que aceptamos como setup/ringback ======
_CSFR_OK_KEYWORDS = ["cifrado", "llamando", "calling", "sonando", "ringing"]
_CONNECTED_RE     = re.compile(r"^\d{1,2}:\d{2}$")  # 0:00, 12:34, etc.

# ====== Botón colgar correcto (tu build) ======
SEL_BOTON_COLGAR = (AppiumBy.ID, "com.whatsapp:id/end_call_button")  # content-desc: "Abandonar la llamada"

def _colgar_seguro(driver, wait_s=5):
    try:
        WebDriverWait(driver, wait_s).until(
            EC.element_to_be_clickable(SEL_BOTON_COLGAR)
        ).click()
        print("[INFO] Llamada colgada.")
    except:
        # fallback por accesibilidad si cambia el id
        try:
            driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Abandonar la llamada").click()
            print("[INFO] Llamada colgada (fallback).")
        except:
            print("[WARN] No se pudo colgar (no visible).")

def medir_csfr(driver, contacto, timeout_setup=25):
    """
    CSFR: éxito si aparece 'cifrado/llamando/sonando' o el reloj (0:00) dentro del timeout.
    Falla si no hay setup dentro del tiempo.
    """
    network = obtener_red_real(driver)
    lat, lon = obtener_gps(driver)
    t0_dt = datetime.now()

    #if not abrir_chat_con(driver, contacto):
    #    csv_write("CSFR", contacto, t0_dt, datetime.now(),
    #              "Failed", "ChatNotFound", network=network, lat=lat, lon=lon)
    #    return

    try:
        _tocar_boton_llamar(driver)
        fin = time.time() + timeout_setup
        ultimo = ""
        ok = False

        while time.time() < fin:
            txt = _leer_subtitulo_llamada(driver)
            if txt and txt != ultimo:
                print(f"[CALL-STATE] {txt}")
                ultimo = txt

            if any(k in txt for k in _CSFR_OK_KEYWORDS):
                ok = True
                break
            if _CONNECTED_RE.match(txt):
                ok = True
                break

            time.sleep(0.2)

        if ok:
            csv_write("CSFR", contacto, t0_dt, datetime.now(),
                      "Successful", "", "setup_ok",
                      network=network, lat=lat, lon=lon)
        else:
            causa = "NoService" if network == "Disconnected" else "NoRingback"
            csv_write("CSFR", contacto, t0_dt, datetime.now(),
                      "Failed", causa, "",
                      network=network, lat=lat, lon=lon)
    finally:
        _colgar_seguro(driver)



# def medir_CSFR(driver, contacto, timeout_conexion=25):
#     """
#     Call Setup Failure Rate: ¿conecta o no dentro del timeout?
#     """
#     network = obtener_red_real(driver); lat, lon = obtener_gps(driver)
#     start = datetime.now()
#     try:
#         if not abrir_chat_con(driver, contacto):
#             csv_write("CSFR", contacto, start, datetime.now(), "Failed", "Item no found", network=network, lat=lat, lon=lon)
#             return
#         # Tap llamada
#         esperar(driver, EC.element_to_be_clickable(SEL_BOTON_LLAMAR), 6).click()
#         # Si no aparece UI de llamada activa → fallo de setup
#         esperar(driver, EC.presence_of_element_located(SEL_ESTADO_EN_LLAMADA), timeout_conexion)
#         csv_write("CSFR", contacto, start, datetime.now(), "Successful",
#                   extra="setup_ok", network=network, lat=lat, lon=lon)
#     except TimeoutException:
#         # Clasifica por red real
#         fail = "No service" if network == "Disconnected" else "Timeout"
#         csv_write("CSFR", contacto, start, datetime.now(), "Failed", fail, network=network, lat=lat, lon=lon)
#     except Exception as e:
#         csv_write("CSFR", contacto, start, datetime.now(), "Failed", str(e), network=network, lat=lat, lon=lon)

# def medir_CDR(driver, contacto, hold_seg=30, timeout_conexion=25):
#     """
#     Call Drop Rate: conectar y sostener X segundos. Si la UI de llamada desaparece antes → drop.
#     """
#     network = obtener_red_real(driver); lat, lon = obtener_gps(driver)
#     start = datetime.now()
#     try:
#         if not abrir_chat_con(driver, contacto):
#             csv_write("CDR", contacto, start, datetime.now(), "Failed", "Item no found", network=network, lat=lat, lon=lon)
#             return
#         esperar(driver, EC.element_to_be_clickable(SEL_BOTON_LLAMAR), 6).click()
#         esperar(driver, EC.presence_of_element_located(SEL_ESTADO_EN_LLAMADA), timeout_conexion)

#         # Ventana de “sostener”
#         t0 = time.time()
#         ok = True
#         while time.time()-t0 < hold_seg:
#             # si en cualquier momento la vista de llamada desaparece => DROP
#             presentes = driver.find_elements(*SEL_ESTADO_EN_LLAMADA)
#             if not presentes:
#                 ok = False
#                 break
#             time.sleep(1)

#         end = datetime.now()
#         if ok:
#             csv_write("CDR", contacto, start, end, "Successful", extra=f"held_s={hold_seg}", network=network, lat=lat, lon=lon)
#         else:
#             csv_write("CDR", contacto, start, end, "Failed", "Dropped", network=network, lat=lat, lon=lon)

#         # Intentar colgar de forma segura
#         try:
#             driver.find_element(*SEL_BOTON_COLGAR).click()
#         except: pass

#     except TimeoutException:
#         csv_write("CDR", contacto, start, datetime.now(), "Failed", "Timeout", network=network, lat=lat, lon=lon)
#     except Exception as e:
#         csv_write("CDR", contacto, start, datetime.now(), "Failed", str(e), network=network, lat=lat, lon=lon)

def sanity_chats(driver, timeout=12):
    try:
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
        contacto = "vast_f"
        if detener:
            return
        medir_cst(driver, contacto)
        medir_csfr(driver, contacto, timeout_setup=25)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()

