import os, csv, time, re, signal, subprocess, socket
from datetime import datetime
from appium import webdriver
from appium.webdriver.common.appiumby import AppiumBy
from appium.options.android import UiAutomator2Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException

# =========================
# Rutas/plan
# =========================
PLAN_TXT = os.path.join(os.path.dirname(__file__), "configuracion.txt")

# =========================
# CONFIG
# =========================
UDID_A = "6NUDU18529000033"  # Dispositivo A
APPIUM_URL_A = "http://127.0.0.1:4723"
# SYSTEM_PORT_A ya no es fijo; se elegirá libre

UDID_B = "6NU7N18614004267"  # Dispositivo B (observer)
APPIUM_URL_B = "http://127.0.0.1:4726"
# SYSTEM_PORT_B ya no es fijo; se elegirá libre

APP_PKG = "com.whatsapp"
APP_ACT = "com.whatsapp.home.ui.HomeActivity"  # fqcn estable

# Variables Globales para Config.txt
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
        if 'run_call' in s or 'run call' in s:
            return 'run_call'
        if ('run' in s) or ('llamar' in s) or ('llamando' in s):
            return 'run_call'
        return None

    with open(path_txt, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith('#'):
                h = line.strip('#').strip().upper()
                if h.startswith('PARAM'):     seccion = 'PARAM'
                elif h.startswith('CONTACTO'): seccion = 'CONTACTO'
                elif h.startswith('PRUEBA'):   seccion = 'PRUEBA'
                else:                          seccion = None
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
CDR_HOLD_S     = 120   # Cambiar a la hora (está en segundos)
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
# Drivers – puertos libres + caps rápidas
# =========================
def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False

def pick_free_port(preferred: int | None = None) -> int:
    if preferred and _port_is_free(preferred):
        return preferred
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    free_port = s.getsockname()[1]
    s.close()
    return free_port

def build_driver(url, udid, system_port, mjpeg_port=None, force_launch=True):
    caps = {
        "platformName": "Android",
        "automationName": "UiAutomator2",
        "deviceName": udid,
        "udid": udid,
        "appPackage": APP_PKG,
        "appActivity": APP_ACT,
        "appWaitActivity": "*",
        "noReset": True,
        "forceAppLaunch": bool(force_launch),
        "systemPort": int(system_port),
        "newCommandTimeout": 360,
        "disableWindowAnimation": True,
        "ignoreHiddenApiPolicyError": True,
        # Speed-ups:
        "skipServerInstallation": True,     # asume server ya instalado (rápido en runs repetidos)
        "skipDeviceInitialization": True,   # evita checks iniciales largos
        # Tiempos generosos para no reintentar en bucle
        "uiautomator2ServerLaunchTimeout": 20000,
        "adbExecTimeout": 20000,
    }
    if mjpeg_port is not None:
        caps["mjpegServerPort"] = int(mjpeg_port)
    options = UiAutomator2Options().load_capabilities(caps)
    drv = webdriver.Remote(command_executor=url, options=options)
    # Tuning runtime para reducir esperas internas de Appium
    try:
        drv.update_settings({
            "waitForIdleTimeout": 0,
            "actionAcknowledgmentTimeout": 0,
            "scrollAcknowledgmentTimeout": 0
        })
    except Exception:
        pass
    return drv

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

CHAT_TITLE_IDS = [
    "com.whatsapp:id/conversation_contact_name",
    "com.whatsapp:id/toolbar_title",
]

RECON_TOKEN = "reconectando"

# =========================
# Señales de finalización
# =========================
detener = False
def manejar_senal(sig, frame):
    global detener
    detener = True
signal.signal(signal.SIGINT, manejar_senal)
signal.signal(signal.SIGTERM, manejar_senal)

# =========================
# Manejar los Chats
# =========================
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
        driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().description("Chats")').click()
        time.sleep(0.3)
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
                    esperar(driver, EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/entry")), 6)
                    return True
            except:
                continue
    except:
        pass

    try:
        driver.find_element(AppiumBy.ID, SEARCH_BAR_ID).click()
        box = driver.switch_to.active_element
        box.clear(); box.send_keys(contacto)
        time.sleep(0.6)
        res = driver.find_elements(AppiumBy.ID, ROW_IDS[0])
        if res:
            res[0].click()
            esperar(driver, EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/entry")), 6)
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
def stable_text(el, ms=220):
    t0 = time.monotonic()
    last = el.text or ""
    while (time.monotonic()-t0)*1000 < ms:
        cur = el.text or ""
        if cur != last:
            t0 = time.monotonic()
            last = cur
        time.sleep(0.02)
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
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((AppiumBy.ACCESSIBILITY_ID, acc))
            ).click()
            try:
                WebDriverWait(driver, 1.5).until(
                    EC.element_to_be_clickable((AppiumBy.ID, "android:id/button1"))
                ).click()
            except:
                pass
            return
        except:
            pass
    try:
        el = WebDriverWait(driver, 2.5).until(EC.element_to_be_clickable((
            AppiumBy.XPATH,
            "//*[contains(@content-desc,'Llam')] | //*[contains(@content-desc,'Call')]"
        )))
        el.click()
    except:
        raise Exception("NoVoiceCallButton")

def colgar_seguro(driver, wait_s=4):
    try:
        card = WebDriverWait(driver, wait_s).until(
            EC.presence_of_element_located((AppiumBy.ID, CALL_CONTROLS_CARD_ID))
        )
        card.find_element(AppiumBy.ID, END_CALL_BTN_ID).click()
        return
    except:
        pass
    try:
        WebDriverWait(driver, 1.5).until(
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
        try:
            still = driver_b.find_elements(AppiumBy.ID, "com.whatsapp:id/accept_incoming_call_view")
            if not still:
                return datetime.now()
        except:
            pass
        return None

    # Tap rápido
    try:
        btns = driver_b.find_elements(AppiumBy.ID, "com.whatsapp:id/accept_incoming_call_view")
        if btns:
            btns[0].click()
            time.sleep(0.35)
            dt = accepted_now_dt()
            if dt:
                _dbg("B contestó (tap).")
                return True, dt
    except:
        pass

    # W3C swipe
    try:
        _dbg("B intenta contestar (W3C swipe).")
        _w3c_swipe_up(driver_b, START_X, START_Y, END_Y, hold_ms=320, move_ms=850)
        time.sleep(0.5)
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
# Para debug
# =========================
DEBUG = True
def _save_pagesource(driver, tag="ps"):
    try:
        xml = driver.page_source
    except Exception as e:
        log(f"no pude guardar pageSource: {e}")
        return
    fn = f"./_debug_{tag}_{int(time.time())}.xml"
    try:
        with open(fn, "w", encoding="utf-8") as f:
            f.write(xml)
        log(f"pageSource guardado en {fn}")
    except Exception as e:
        log(f"no pude guardar pageSource en disco: {e}")

def log(msg):
    if DEBUG:
        print(f"[DBG] {msg}")

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

# ============ ADB + PCAPdroid ============
def _run_adb_shell(adb_serial: str, cmd: str, timeout_s: float = 8.0):
    try:
        subprocess.run(
            ["adb", "-s", adb_serial, "shell"] + cmd.split(),
            check=True, timeout=timeout_s,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError as e:
        if DEBUG:
            print(f"[DBG] ADB shell error: {cmd} -> {e}")
    except subprocess.TimeoutExpired:
        if DEBUG:
            print(f"[DBG] ADB shell timeout: {cmd}")

def _pcapdroid_start(adb_serial: str, start_xy=(534, 870), settle_s=0.6):
    _run_adb_shell(adb_serial, "am start -n com.emanuelef.remote_capture/com.emanuelef.remote_capture.activities.MainActivity")
    time.sleep(settle_s)
    _run_adb_shell(adb_serial, f"input tap {start_xy[0]} {start_xy[1]}")
    if 'log_evt' in globals():
        log_evt("PCAP_START", datetime.now(), f"serial={adb_serial};xy={start_xy[0]},{start_xy[1]}")

def _pcapdroid_stop(adb_serial: str, stop_xy=(735, 170), settle_s=0.5):
    _run_adb_shell(adb_serial, "am start -n com.emanuelef.remote_capture/com.emanuelef.remote_capture.activities.MainActivity")
    time.sleep(settle_s)
    _run_adb_shell(adb_serial, f"input tap {stop_xy[0]} {stop_xy[1]}")
    if 'log_evt' in globals():
        log_evt("PCAP_STOP", datetime.now(), f"serial={adb_serial};xy={stop_xy[0]},{stop_xy[1]}")

def _switch_to_whatsapp(adb_serial: str, settle_s=0.5):
    _run_adb_shell(adb_serial, "am start -n com.whatsapp/com.whatsapp.home.ui.HomeActivity")
    time.sleep(settle_s)
    if 'log_evt' in globals():
        log_evt("APP_SWITCH", datetime.now(), "to=WhatsApp")

# ============ Auto-heal de UiAutomator2 ============
def _is_instrumentation_dead(exc: Exception) -> bool:
    s = str(exc).lower()
    return ("instrumentation process is not running" in s) or ("uiautomator2" in s and "not running" in s)

def heal_driver(driver, role: str):
    try:
        _ = driver.get_window_size()
        return driver  # sano
    except Exception as e:
        if not _is_instrumentation_dead(e):
            return driver  # otro error, no tocamos
    # instrumentation muerto -> recrear
    try:
        driver.quit()
    except:
        pass
    time.sleep(0.8)
    if role == 'A':
        sysp = pick_free_port(8206)
        mjpg = pick_free_port(7830)
        return build_driver(APPIUM_URL_A, UDID_A, sysp, mjpeg_port=mjpg, force_launch=False)
    else:
        sysp = pick_free_port(8212)
        mjpg = pick_free_port(7832)
        return build_driver(APPIUM_URL_B, UDID_B, sysp, mjpeg_port=mjpg, force_launch=False)

# ============ Readiness de WhatsApp ============
def wait_whatsapp_ready(driver, contacto: str, timeout_s=10) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        try:
            if is_in_chats_list(driver) or is_in_chat_with(driver, contacto):
                return True
            driver.activate_app(APP_PKG)
        except:
            pass
        time.sleep(0.35)
    return False

# ------------------------------------------------------------
# Versión integrada de run_call(...)
# ------------------------------------------------------------
def run_call(
    driver_a, driver_b, contacto,
    hold_s=CDR_HOLD_S, drop_grace=DROP_GRACE_S, auto_answer_b=True,
    # --- NUEVOS PARAMS PARA PCAPdroid/ADB ---
    use_pcapdroid=True,
    adb_serial=UDID_A,
    pcapdroid_start_xy=(534, 870),
    pcapdroid_stop_xy=(735, 170),
    settle_after_switch_s=0.5
):
    """
    Ejecuta una sesión de llamada (KPIs: CALL_ATTEMPT, B_ANSWER, CALL_CONNECTED, CDR, RECON spans)
    con captura PCAP (PCAPdroid) alrededor del ciclo.
    """
# START PCAP (sí con ADB) pero el switch de regreso a WhatsApp será por Appium
    if use_pcapdroid:
        try:
            _pcapdroid_start(adb_serial, start_xy=pcapdroid_start_xy)
        except Exception as e:
            if DEBUG:
                print(f"[DBG] PCAP start failed: {e}")

    # 1) Repara driver si UiAutomator2 murió
    driver_a = heal_driver(driver_a, role='A')

    # 2) Trae WhatsApp al frente SOLO con Appium (no ADB) y espera foreground
    switch_to_whatsapp_via_appium(driver_a)

    # 3) (Opcional) espera light a que la UI esté accesible
    # evita bloqueos largos; si no está lista, igualmente ensure_chat_open hará reintentos

    try:
        # 1) Abrir chat
        log("[RUN] ensure_chat_open(start)")
        ok = ensure_chat_open(driver_a, contacto)
        log("[RUN] ensure_chat_open(done) -> " + str(ok))
        if not ok:
            _save_pagesource(driver_a, "cdr_chatnotfound")
            tnow = datetime.now()
            network = obtener_red_real(driver_a)
            lat, lon = obtener_gps(UDID_A)
            csv_write("CDR", contacto, tnow, tnow, "Failed", "ChatNotFound", "", network, lat, lon)
            log_evt("CDR_FAIL", tnow, "ChatNotFound")
            return

        # 2) Contexto
        network = obtener_red_real(driver_a)
        lat, lon = obtener_gps(UDID_A)

        # 3) CALL_ATTEMPT
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

        t0_dt = t_press_dt

        # 4) B_ANSWER (auto)
        answered_dt = None
        if auto_answer_b:
            driver_b = heal_driver(driver_b, role='B')
            answered, answered_dt = answer_incoming_call_b(driver_b, wait_s=12)
            if answered and answered_dt:
                csv_write("B_ANSWER", contacto, answered_dt, answered_dt, "Event", "", "", network, lat, lon)
                log_evt("B_ANSWER", answered_dt)

        # 5) CALL_CONNECTED (mm:ss)
        connected_dt = None
        t_deadline = time.monotonic() + 22.0
        while time.monotonic() < t_deadline and not detener:
            txt = find_subtitle_text(driver_a)
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
            time.sleep(0.18)

        if not connected_dt:
            now_dt = datetime.now()
            csv_write("CDR", contacto, t0_dt, now_dt, "Failed", "NotConnected", "", network, lat, lon)
            log_evt("CDR_FAIL", now_dt, "NotConnected")
            colgar_seguro(driver_a)
            return

        # Reconectando A/B durante el hold
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
                    if DEBUG: print(f"[DBG] [EVT] RECON_A start @ {recon_start_A.strftime('%H:%M:%S')}")
                elif (not is_recon) and recon_active_A:
                    recon_active_A = False
                    end_dt = datetime.now()
                    recon_spans_A.append((recon_start_A, end_dt))
                    if DEBUG: print(f"[DBG] [EVT] RECON_A end @ {end_dt.strftime('%H:%M:%S')} | dur={(end_dt - recon_start_A).total_seconds():.2f}s")
                    recon_start_A = None
            else:
                if is_recon and not recon_active_B:
                    recon_active_B = True
                    recon_start_B = datetime.now()
                    if DEBUG: print(f"[DBG] [EVT] RECON_B start @ {recon_start_B.strftime('%H:%M:%S')}")
                elif (not is_recon) and recon_active_B:
                    recon_active_B = False
                    end_dt = datetime.now()
                    recon_spans_B.append((recon_start_B, end_dt))
                    if DEBUG: print(f"[DBG] [EVT] RECON_B end @ {end_dt.strftime('%H:%M:%S')} | dur={(end_dt - recon_start_B).total_seconds():.2f}s")
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

            time.sleep(0.22)

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

    finally:
        if use_pcapdroid:
            try:
                _pcapdroid_stop(adb_serial, stop_xy=pcapdroid_stop_xy)
            except Exception as e:
                if DEBUG:
                    print(f"[DBG] PCAP stop failed: {e}")

# =========================
# MAIN
# =========================
def main():
    pruebas = leer_plan_config(PLAN_TXT)
    if not pruebas:
        print("[RUN] No hay pruebas en configuracion.txt")
        return

    csv_init()

    # Puertos libres y distintos por dispositivo
    sys_a = pick_free_port(8206)
    mjpeg_a = pick_free_port(7830)
    sys_b = pick_free_port(8212)
    if sys_b == sys_a: sys_b = pick_free_port()
    mjpeg_b = pick_free_port(7832)
    if mjpeg_b == mjpeg_a: mjpeg_b = pick_free_port()

    print(f"[PORTS] A: systemPort={sys_a}, mjpegServerPort={mjpeg_a}")
    print(f"[PORTS] B: systemPort={sys_b}, mjpegServerPort={mjpeg_b}")

    driver_a = build_driver(APPIUM_URL_A, UDID_A, sys_a, mjpeg_port=mjpeg_a, force_launch=True)
    driver_b = build_driver(APPIUM_URL_B, UDID_B, sys_b, mjpeg_port=mjpeg_b, force_launch=False)

    try:
        for i, accion in enumerate(pruebas, 1):
            print(f"[RUN] Comenzando {accion.upper()} para '{CONTACTO}'...")
            # Sanar drivers por si el ciclo anterior mató UiAutomator2
            driver_a = heal_driver(driver_a, 'A')
            driver_b = heal_driver(driver_b, 'B')

            if accion == 'run_call':
                run_call(
                    driver_a, driver_b, CONTACTO,
                    hold_s=CDR_HOLD_S,
                    drop_grace=DROP_GRACE_S,
                    auto_answer_b=True,
                    adb_serial=UDID_A   # A es quien inicia/para PCAPdroid
                )
            elif accion == 'cdr':
                print("measure_cdr (placeholder)")
            elif accion == 'cst_csfr':
                print("measure_cst_csfr (placeholder)")

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

def wait_app_foreground(driver, pkg: str, act: str, timeout_s=8) -> bool:
    """
    Garantiza que (pkg/act) están en primer plano usando SOLO Appium.
    Evita usar ADB aquí para no romper UiAutomator2.
    """
    t0 = time.monotonic()
    last_pkg = None
    while time.monotonic() - t0 < timeout_s:
        try:
            cur_pkg = getattr(driver, "current_package", None)
            if cur_pkg:
                last_pkg = cur_pkg
            if cur_pkg == pkg:
                return True
            # traer la app con APIs de Appium (no ADB)
            try:
                driver.activate_app(pkg)
            except Exception:
                try:
                    driver.start_activity(pkg, act)
                except Exception:
                    pass
        except Exception:
            # reintento suave
            try:
                driver.start_activity(pkg, act)
            except Exception:
                pass
        time.sleep(0.35)
    if DEBUG:
        print(f"[DBG] wait_app_foreground timeout; last_pkg={last_pkg}")
    return False


def switch_to_whatsapp_via_appium(driver):
    """
    Trae WhatsApp al frente de forma 'in-band' (Appium),
    y espera a que esté listo para interactuar.
    """
    ok_fg = wait_app_foreground(driver, APP_PKG, APP_ACT, timeout_s=8)
    if not ok_fg and DEBUG:
        print("[DBG] WhatsApp no quedó foreground con start_activity/activate_app")

    # Pequeña espera y verificación de UI 'ligera'
    # (evitamos find_elements agresivos de inicio)
    time.sleep(0.4)











if __name__ == "__main__":
    main()
