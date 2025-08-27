# -*- coding: utf-8 -*-
import os, csv, time, re, signal
from datetime import datetime

from appium import webdriver
from appium.webdriver.common.appiumby import AppiumBy
from appium.options.android import UiAutomator2Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

PLAN_TXT = os.path.join(os.path.dirname(__file__), "configuracion.txt")
DEBUG = True
def log(msg):
    if DEBUG:
        print(f"[DBG] {msg}")

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

#Varibales
CONTACTO = "0"
TIEMPO_ENTRE_CICLOS = 0

import shlex

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
                # primera línea no vacía
                if line:
                    CONTACTO = line.strip()
                continue

            if seccion == 'PRUEBA':
                act = normaliza_prueba(line)
                if act:
                    pruebas_norm.append(act)
                else:
                    print(f"[WARN] Prueba desconocida: {line}")
                continue

    if not pruebas_norm:
        print("[PLAN] No hay pruebas en #PRUEBAS.")
    return pruebas_norm




# Timeouts / parámetros
CST_TIMEOUT_S  = 20.0   # ventana para detectar setup en A
CSFR_TIMEOUT_S = 20.0   # ventana para ver entrante en B
CDR_HOLD_S     = 30.0   # sostener llamada conectada
DROP_GRACE_S   = 2.0    # tolerancia para considerar Drop si desaparece UI

# CSV extendido
timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
CSV_PATH = f"./WhatsApp_KPIs_{timestamp}.csv"
CSV_HEADER = ["App","Network","KPI","Contact",
              "Latitude","Longitude",
              "Start","End","Result","Failure","Extra"]

# IDs/Selectores (tu build)
# Lista de chats
ROW_IDS = ["com.whatsapp:id/contact_row_container"]
#ROW_HEADER_ID = "com.whatsapp:id/conversations_row_header"
ROW_HEADER_ID = "com.whatsapp:id/conversations_row_contact_name"
# Buscador
SEARCH_BAR_ID = "com.whatsapp:id/my_search_bar"

# Botón de llamada
VOICE_CALL_ACCS = ("Llamada",)

# Llamada (A)
CALL_HEADER_ID        = "com.whatsapp:id/call_screen_header_view"
CALL_SUBTITLE_ID      = "com.whatsapp:id/subtitle"
CALL_CONTROLS_CARD_ID = "com.whatsapp:id/call_controls_card"
END_CALL_BTN_ID       = "com.whatsapp:id/end_call_button"

# Entrante (B)
B_CALL_ROOT_ID         = "com.whatsapp:id/call_screen_root"
B_ANSWER_ROOT_ID       = "com.whatsapp:id/answer_call_view_id"
B_ACCEPT_CONTAINER_ID  = "com.whatsapp:id/accept_incoming_call_container"
B_ACCEPT_SWIPE_HINT_ID = "com.whatsapp:id/accept_call_swipe_up_hint_view"
B_ACCEPT_BUTTON_ID     = "com.whatsapp:id/accept_incoming_call_view"

# Estado/subtítulo
_CONNECTED_RE      = re.compile(r"^\d{1,2}:\d{2}$")  # 0:00..59:59
SUBTITLE_POSITIVES = ("cifrado", "llamando", "calling", "sonando", "ringing")

# Señales
detener = False
def manejar_senal(sig, frame):
    global detener
    print("\n[INFO] Señal recibida, deteniendo con gracia...")
    detener = True
signal.signal(signal.SIGINT, manejar_senal)
signal.signal(signal.SIGTERM, manejar_senal)

# =========================
# CSV helpers
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
# Navegación / selección
# (orden: lista de chats -> dentro del chat)
# =========================

# def is_in_chats_list(driver) -> bool:
#     try:
#         if driver.find_elements(AppiumBy.ID, ROW_IDS[0]):
#             return True
#     except:
#         pass
#     try:
#         driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR,
#             'new UiSelector().description("Chats")')
#         return True
#     except:
#         return False

def is_in_chats_list(driver) -> bool:
    try:
        els = driver.find_elements(AppiumBy.ID, ROW_IDS[0])
        log(f"is_in_chats_list: ROW_IDS[0]='{ROW_IDS[0]}' -> {len(els)} elementos")
        if els:
            return True
    except Exception as e:
        log(f"is_in_chats_list EXC en {ROW_IDS[0]}: {e}")

    try:
        driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().description("Chats")')
        log('is_in_chats_list: description("Chats") presente')
        return True
    except Exception:
        # No imprimas stacktrace aquí; es normal si ya estás dentro de un chat
        log('is_in_chats_list: pestaña "Chats" no visible (normal si estás dentro de un chat)')
        return False



CHAT_TITLE_IDS = [
    "com.whatsapp:id/conversation_contact_name",
    "com.whatsapp:id/toolbar_title",
]

def is_in_chat_with(driver, contacto: str) -> bool:
    has_entry = False
    try:
        has_entry = bool(driver.find_elements(AppiumBy.ID, "com.whatsapp:id/entry"))
        log(f"is_in_chat_with: entry presente={has_entry}")
    except Exception as e:
        log(f"is_in_chat_with: error buscando entry: {e}")
        return False
    if not has_entry:
        return False

    for tid in CHAT_TITLE_IDS:
        try:
            t = (driver.find_element(AppiumBy.ID, tid).text or "").strip()
            log(f"is_in_chat_with: {tid}='{t}' vs contacto='{contacto}'")
            if t and contacto.lower() in t.lower():
                return True
        except Exception as e:
            log(f"is_in_chat_with: no pude leer {tid}: {e}")
            continue
    return False

# def is_in_chat_with(driver, contacto: str) -> bool:
#     try:
#         has_entry = bool(driver.find_elements(AppiumBy.ID, "com.whatsapp:id/entry"))
#         if not has_entry:
#             return False
#     except:
#         return False
#     for tid in CHAT_TITLE_IDS:
#         try:
#             t = (driver.find_element(AppiumBy.ID, tid).text or "").strip()
#             if t and contacto.lower() in t.lower():
#                 return True
#         except:
#             continue
#     return False

def go_to_chats_tab(driver):
    try:
        driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR,
            'new UiSelector().description("Chats")').click()
        time.sleep(0.5)
    except:
        pass

def open_chat(driver, contacto: str) -> bool:
    # 1) lista visible
    try:
        filas = driver.find_elements(AppiumBy.ID, ROW_IDS[0])
        log(f"open_chat: filas con {ROW_IDS[0]} = {len(filas)}")
        for i, fila in enumerate(filas):
            try:
                header = fila.find_element(AppiumBy.ID, ROW_HEADER_ID)
                nombre = (header.text or "").strip()
                log(f"open_chat: fila[{i}] header='{nombre}'")
                if contacto.lower() in (nombre or "").lower():
                    fila.click()
                    log("open_chat: click fila -> esperando entry")
                    esperar(driver, EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/entry")), 8)
                    return True
            except Exception as e:
                log(f"open_chat: fila[{i}] sin header {ROW_HEADER_ID}: {e}")
                continue
    except Exception as e:
        log(f"open_chat: error listando filas {ROW_IDS[0]}: {e}")

    # 2) búsqueda
    try:
        log(f"open_chat: tocando barra de búsqueda {SEARCH_BAR_ID}")
        driver.find_element(AppiumBy.ID, SEARCH_BAR_ID).click()
        box = driver.switch_to.active_element
        box.clear(); box.send_keys(contacto)
        time.sleep(1.0)
        res = driver.find_elements(AppiumBy.ID, ROW_IDS[0])
        log(f"open_chat: resultados búsqueda con {ROW_IDS[0]} = {len(res)}")
        if res:
            res[0].click()
            esperar(driver, EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/entry")), 8)
            return True
    except Exception as e:
        log(f"open_chat: búsqueda falló (id {SEARCH_BAR_ID}?): {e}")
        _save_pagesource(driver, "search_fail")  # para ver IDs reales en tu build

    return False


# def open_chat(driver, contacto: str) -> bool:
#     # lista visible
#     try:
#         filas = driver.find_elements(AppiumBy.ID, ROW_IDS[0])
#         for fila in filas:
#             try:
#                 header = fila.find_element(AppiumBy.ID, ROW_HEADER_ID)
#                 nombre = (header.text or "").strip()
#                 if contacto.lower() in nombre.lower():
#                     fila.click()
#                     esperar(driver, EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/entry")), 8)
#                     return True
#             except:
#                 continue
#     except:
#         pass
#     # búsqueda
#     try:
#         driver.find_element(AppiumBy.ID, SEARCH_BAR_ID).click()
#         box = driver.switch_to.active_element  # EditText activo
#         box.clear(); box.send_keys(contacto)
#         time.sleep(1.0)
#         res = driver.find_elements(AppiumBy.ID, ROW_IDS[0])
#         if res:
#             res[0].click()
#             esperar(driver, EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/entry")), 8)
#             return True
#     except:
#         pass
#     return False

# def ensure_chat_open(driver, contacto: str) -> bool:
#     # 1) primero lista de chats
#     if is_in_chats_list(driver):
#         if open_chat(driver, contacto):
#             return True
#     # 2) si no, ya dentro del chat correcto
#     if is_in_chat_with(driver, contacto):
#         return True
#     # 3) ir a pestaña Chats y abrir
#     go_to_chats_tab(driver)
#     return open_chat(driver, contacto)
def ensure_chat_open(driver, contacto: str) -> bool:
    log("ensure_chat_open: inicio")

    # 0) Ya estoy dentro del chat (evita buscar la lista/pestaña innecesariamente)
    if is_in_chat_with(driver, contacto):
        log("ensure_chat_open: ya estoy dentro del chat correcto")
        return True

    # 1) Lista visible -> abrir chat
    if is_in_chats_list(driver):
        log("ensure_chat_open: estoy en lista -> intento open_chat")
        ok = open_chat(driver, contacto)
        log(f"ensure_chat_open: open_chat -> {ok}")
        return ok

    # 2) Ir a pestaña 'Chats' y reintentar
    log('ensure_chat_open: intentando ir a pestaña "Chats"')
    go_to_chats_tab(driver)
    ok = open_chat(driver, contacto)
    log(f"ensure_chat_open: open_chat (tras cambiar de tab) -> {ok}")
    if ok:
        return True

    _save_pagesource(driver, "ensure_fail")
    return False


def _save_pagesource(driver, tag="ps"):
    try:
        xml = driver.page_source
        fn = f"./_debug_{tag}_{int(time.time())}.xml"
        with open(fn, "w", encoding="utf-8") as f:
            f.write(xml)
        log(f"pageSource guardado en {fn}")
    except Exception as e:
        log(f"no pude guardar pageSource: {e}")
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
    # accesibilidad directa
    for acc in VOICE_CALL_ACCS:
        try:
            WebDriverWait(driver, 6).until(
                EC.element_to_be_clickable((AppiumBy.ACCESSIBILITY_ID, acc))
            ).click()
            # confirmar (si aparece)
            try:
                WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((AppiumBy.ID, "android:id/button1"))
                ).click()
            except:
                pass
            return
        except:
            pass
    # fallback por XPath de content-desc
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
# Auto-answer en B (swipe up robusto)
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

    # 1) W3C actions
    try:
        _w3c_swipe_up(driver_b, sx, sy, ey, hold_ms=320, move_ms=800)
        time.sleep(0.6)
        return True
    except:
        pass

    # 2) dragGesture
    try:
        _drag_up_via_gesture(driver_b, el, pct=0.75, duration=850)
        time.sleep(0.5)
        return True
    except:
        pass

    # 3) ADB swipe
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

def answer_incoming_call_b(driver_b, wait_s=14) -> bool:
    """
    Contesta la llamada entrante en B usando coordenadas fijas:
    start=(540,1918) -> end=(540,273).
    Intenta en orden: dragGesture -> W3C actions -> adb swipe.
    Retorna True si el botón de aceptar desaparece (aceptó).
    """
    # Si la tienes definida en tu script, ayuda a evitar lockscreen/ambiente dormido:
    try:
        wake_and_dismiss_keyguard(driver_b)
    except:
        pass

    START_X, START_Y = 540, 1918
    END_X,   END_Y   = 540, 273

    t_end = time.monotonic() + wait_s

    def accepted_now() -> bool:
        """Consideramos aceptado si ya no vemos el botón de aceptar."""
        try:
            return not driver_b.find_elements(AppiumBy.ID, "com.whatsapp:id/accept_incoming_call_view")
        except:
            return False

    # --- Intento 0: (opcional) click rápido, por si tu variante lo permite ---
    try:
        btns = driver_b.find_elements(AppiumBy.ID, "com.whatsapp:id/accept_incoming_call_view")
        if btns:
            btns[0].click()
            time.sleep(0.4)
            if accepted_now():
                return True
    except:
        pass

    # --- Intento 1: dragGesture por coordenadas ---
    try:
        print("Contesto B")
        driver_b.execute_script("mobile: dragGesture", {
            "startX": int(START_X),
            "startY": int(START_Y),
            "endX":   int(END_X),
            "endY":   int(END_Y),
            "duration": 900  # ms
        })
        time.sleep(0.6)
        if accepted_now():
            return True
    except:
        pass

    # --- Intento 2: W3C actions (press-hold-move-release) ---
    try:
        print("contesto 2")
        actions = [{
            "type": "pointer",
            "id": "finger1",
            "parameters": {"pointerType": "touch"},
            "actions": [
                {"type": "pointerMove", "duration": 0, "x": int(START_X), "y": int(START_Y)},
                {"type": "pointerDown", "button": 0},
                {"type": "pause", "duration": 350},
                {"type": "pointerMove", "duration": 900, "x": int(END_X), "y": int(END_Y)},
                {"type": "pointerUp", "button": 0},
            ],
        }]
        driver_b.perform_actions(actions)
        try:
            driver_b.release_actions()
        except:
            pass
        time.sleep(0.6)
        if accepted_now():
            return True
    except:
        pass

    # Reintentos ligeros dentro de la ventana wait_s, por si la UI tardó en pintar
    while time.monotonic() < t_end:
        if accepted_now():
            return True
        time.sleep(0.2)

    return False


# =========================
# Métricas separadas
# =========================
def measure_cst_csfr(driver_a, driver_b, contacto,
                     cst_timeout=CST_TIMEOUT_S,
                     csfr_timeout=CSFR_TIMEOUT_S):
#TAMBIEN
    log(f"[CST/CSFR] contacto='{contacto}'")
    ok = ensure_chat_open(driver_a, contacto)
    log(f"[CST/CSFR] ensure_chat_open -> {ok}")
    if not ok:
        _save_pagesource(driver_a, "cst_csfr_chatnotfound")
        now_dt = datetime.now()
        network = obtener_red_real(driver_a)
        lat, lon = obtener_gps(driver_a)
        csv_write("CST",  contacto, now_dt, now_dt, "Failed", "ChatNotFound", network=network, lat=lat, lon=lon)
        csv_write("CSFR", contacto, now_dt, now_dt, "Failed", "ChatNotFound", network=network, lat=lat, lon=lon)
        return
#AGREGADO RECIEN
    network = obtener_red_real(driver_a)
    lat, lon = obtener_gps(driver_a)
    t0_dt = datetime.now()

    if not ensure_chat_open(driver_a, contacto):
        now_dt = datetime.now()
        csv_write("CST",  contacto, t0_dt, now_dt, "Failed", "ChatNotFound", network=network, lat=lat, lon=lon)
        csv_write("CSFR", contacto, t0_dt, now_dt, "Failed", "ChatNotFound", network=network, lat=lat, lon=lon)
        return

    # Iniciar llamada
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

    # Poll para CST (subtitle con keywords o mm:ss)
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


    # CSFR (B: entrante fullscreen presente)
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

    # CSV: CST
    if cst_done and cst_t is not None:
        cst_val = max(0.0, cst_t - press_t)
        csv_write("CST", contacto, t0_dt, end_dt, "Successful", "",
                  f"setup_s={cst_val:.2f};trigger=A:{cst_trigger}",
                  network=network, lat=lat, lon=lon)
    else:
        causa = "NoSetupLabel" if network != "Disconnected" else "NoService"
        csv_write("CST", contacto, t0_dt, end_dt, "Failed", causa, "", network=network, lat=lat, lon=lon)

    # CSV: CSFR
    if csfr_done:
        csv_write("CSFR", contacto, t0_dt, end_dt, "Successful", "", "incoming_on_B:fullscreen",
                  network=network, lat=lat, lon=lon)
    else:
        csv_write("CSFR", contacto, t0_dt, end_dt, "Failed", "NoIncomingOnB", "",
                  network=network, lat=lat, lon=lon)

    # cortar llamada para esta función (no mide CDR)
    colgar_seguro(driver_a)

def measure_cdr(driver_a, driver_b, contacto,
                hold_s=CDR_HOLD_S, drop_grace=DROP_GRACE_S,
                auto_answer_b=True):
    #DESDEACA
    log(f"[CDR] contacto='{contacto}'")
    ok = ensure_chat_open(driver_a, contacto)
    log(f"[CDR] ensure_chat_open -> {ok}")
    if not ok:
        _save_pagesource(driver_a, "cdr_chatnotfound")
        tnow = datetime.now()
        network = obtener_red_real(driver_a)
        lat, lon = obtener_gps(driver_a)
        csv_write("CDR", contacto, tnow, tnow, "Failed", "ChatNotFound", "", network, lat, lon)
        return
    # (lo demás igual…)

    network = obtener_red_real(driver_a)
    lat, lon = obtener_gps(driver_a)
    t0_dt = datetime.now()

    if not ensure_chat_open(driver_a, contacto):
        csv_write("CDR", contacto, t0_dt, datetime.now(), "Failed", "ChatNotFound", "",
                  network, lat, lon)
        return

    try:
        tocar_boton_llamar(driver_a)
    except Exception as e:
        csv_write("CDR", contacto, t0_dt, datetime.now(), "Failed", f"NoCallBtn:{e}", "",
                  network, lat, lon)
        return

    # Permitir que B conteste automáticamente si se solicita
    if auto_answer_b:
        answered = answer_incoming_call_b(driver_b, wait_s=14)
        if not answered:
            # Último intento: si aún vemos UI de entrante, repetir swipe con otro elemento
            try:
                alt = None
                try:
                    alt = driver_b.find_element(AppiumBy.ID, B_ACCEPT_CONTAINER_ID)
                except:
                    alt = driver_b.find_element(AppiumBy.ID, B_ACCEPT_SWIPE_HINT_ID)
                _swipe_up_element_robust(driver_b, alt)
            except:
                pass

    # esperar conexión (mm:ss)
    connected_t = None
    t_deadline = time.monotonic() + 25.0
    while time.monotonic() < t_deadline and not detener:
        txt = find_subtitle_text(driver_a)
        if _CONNECTED_RE.match(txt or ""):
            connected_t = time.monotonic()
            break
        time.sleep(0.2)

    if not connected_t:
        csv_write("CDR", contacto, t0_dt, datetime.now(), "Failed", "NotConnected", "",
                  network, lat, lon)
        colgar_seguro(driver_a)
        return

    # sostener: si desaparece la UI de llamada > grace => Dropped
    hold_deadline = time.monotonic() + float(hold_s)
    missing_since = None
    dropped = False
    while time.monotonic() < hold_deadline and not detener:
        alive = False
        try:
            txt = find_subtitle_text(driver_a)
            if txt:
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
                  f"held_s≈{int(hold_s - max(0, hold_deadline - time.monotonic()))}",
                  network, lat, lon)
    else:
        csv_write("CDR", contacto, t0_dt, end_dt, "Successful", "",
                  f"held_s={int(hold_s)}", network, lat, lon)

    colgar_seguro(driver_a)

def test_selectores():
    leer_plan_config(PLAN_TXT)
    driver = build_driver(APPIUM_URL_A, UDID_A, SYSTEM_PORT_A, force_launch=True)
    try:
        log("=== TEST SELECTORES ===")
        log(f"CONTACTO='{CONTACTO}'")
        # 1) ¿Veo lista?
        log("Paso 1: is_in_chats_list")
        _ = is_in_chats_list(driver)

        # 2) Intento abrir
        log("Paso 2: ensure_chat_open")
        ok = ensure_chat_open(driver, CONTACTO)
        log(f"Resultado ensure_chat_open={ok}")

        # 3) Si falla, ya quedó un _debug_*.xml con el pageSource
        #    Ábrelo y busca cómo se llaman realmente los IDs en tu build.
    finally:
        try: driver.quit()
        except: pass

def main():
    log(f"Usaré plan: {PLAN_TXT}")
    pruebas = leer_plan_config(PLAN_TXT)
    log(f"CONTACTO (desde TXT) = '{CONTACTO}'")
    log(f"TIEMPO_ENTRE_CICLOS   = {TIEMPO_ENTRE_CICLOS}")
    log(f"PRUEBAS normalizadas  = {pruebas}")

    if not pruebas:
        log("[ERROR] No hay pruebas en el plan. Saliendo.")
        return

    csv_init()

    driver_a = build_driver(APPIUM_URL_A, UDID_A, SYSTEM_PORT_A, force_launch=True)
    driver_b = build_driver(APPIUM_URL_B, UDID_B, SYSTEM_PORT_B, force_launch=False)
    log(f"Drivers OK: A={UDID_A} @ {APPIUM_URL_A} / B={UDID_B} @ {APPIUM_URL_B}")

    try:
        for i, accion in enumerate(pruebas, 1):
            log(f"[PLAN] Paso {i}/{len(pruebas)}: {accion} -> contacto='{CONTACTO}'")
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

            if i < len(pruebas):
                try:
                    log(f"Dormir {TIEMPO_ENTRE_CICLOS}s antes del siguiente paso...")
                    time.sleep(float(TIEMPO_ENTRE_CICLOS))
                except Exception:
                    pass
    finally:
        for d in (driver_a, driver_b):
            try: d.quit()
            except: pass

if __name__ == "__main__":
    main()

# =========================
# MAIN
# =========================
# def main():
#     # Lee archivo de configuración antes de todo
#     PLAN_TXT = "configuracion.txt"   # ajusta ruta si hace falta
#     pruebas = leer_plan_config(PLAN_TXT)
#     if not pruebas:
#         return

#     csv_init()

#     driver_a = build_driver(APPIUM_URL_A, UDID_A, SYSTEM_PORT_A, force_launch=True)
#     driver_b = build_driver(APPIUM_URL_B, UDID_B, SYSTEM_PORT_B, force_launch=False)

#     try:
#         for i, accion in enumerate(pruebas, 1):
#             print(f"[PLAN] Paso {i}: {accion} -> contacto={CONTACTO}")
#             if accion == 'cst_csfr':
#                 measure_cst_csfr(
#                     driver_a, driver_b, CONTACTO,
#                     cst_timeout=CST_TIMEOUT_S,
#                     csfr_timeout=CSFR_TIMEOUT_S
#                 )
#             elif accion == 'cdr':
#                 measure_cdr(
#                     driver_a, driver_b, CONTACTO,
#                     hold_s=CDR_HOLD_S,
#                     drop_grace=DROP_GRACE_S,
#                     auto_answer_b=True
#                 )
#             # sleep entre pruebas (no después de la última, pero si quieres también, quita el if)
#             if i < len(pruebas):
#                 try:
#                     time.sleep(float(TIEMPO_ENTRE_CICLOS))
#                 except Exception:
#                     pass
#     finally:
#         for d in (driver_a, driver_b):
#             try: d.quit()
#             except: pass


# if __name__ == "__main__":
#     main()




















"""
    Formato:
    #PARAMETROS
    tiempo_entre_ciclos=5

    #CONTACTO
    vast_wa

    #PRUEBAS
    CST y CSFR
    CDR
"""