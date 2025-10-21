# -*- coding: utf-8 -*-
from appium import webdriver
from appium.options.android import UiAutomator2Options
from datetime import datetime, timezone
from io import BytesIO
from PIL import Image
import pytesseract
import time, csv, os, subprocess, re, signal, shutil
from gnettrack import iniciar_logs

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --------- Tesseract (auto) ----------
pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract") or "/usr/bin/tesseract"

# ========== CONFIGURACION INICIAL ==========
detener = False

def detener_flag():
    global detener
    print("[INFO] Proceso detenido.")
    detener = True

signal.signal(signal.SIGTERM, lambda s, f: detener_flag())
signal.signal(signal.SIGINT,  lambda s, f: detener_flag())

METRICAS = {"FEED": "Feed loading", "RVIDEO": "Short video playback"}


# Límites por tipo de prueba (segundos)
LIMITES_SEG = {
    METRICAS["FEED"]: 7,     # Feed loading: 7 s
    METRICAS["RVIDEO"]: 10,  # Short video playback (reels): 10 s
}

def get_limite(metric_type: str) -> int:
    """Devuelve el límite (en segundos) para el tipo de métrica. Default: 10 s."""
    return LIMITES_SEG.get(metric_type, 10)

BROWSER_PACKAGE = os.getenv("ALVA_PKG", "org.oyealva.stable")
UDID = os.getenv("UDID", "R58M795NHZF")

caps = {
    "platformName": "Android",
    "deviceName": UDID,
    "udid": UDID,
    "automationName": "UiAutomator2",
    "appPackage": BROWSER_PACKAGE,
    "forceAppLaunch": True,
    "systemPort": 8230,
    "noReset": True,
    "newCommandTimeout": 360
}

# ========== FUNCIONES DE TIEMPO ==========
from datetime import datetime as _dt_for_device_now

def device_now_via_appium(driver) -> _dt_for_device_now:
    try:
        res = driver.execute_script("mobile: shell", {
            "command": "date",
            "args": ["+%s"],
            "timeout": 5000,
            "includeStderr": True
        })
        s = (res or {}).get("stdout", "").strip()
        if s.isdigit():
            return _dt_for_device_now.fromtimestamp(int(s))
    except Exception:
        pass
    return _dt_for_device_now.now()

def device_timestamp_str(driver) -> str:
    dt = device_now_via_appium(driver)
    return dt.strftime("%Y-%m-%d %H:%M:%S") + ".000"

def device_stamp_for_filename(driver) -> str:
    dt = device_now_via_appium(driver)
    return dt.strftime("%Y_%m_%d_%H%M%S")

# ========== UTILIDADES ==========
def inicializar_csv(driver):
    global CSV_PATH_IG, CSV_PATH_FB
    ts = device_stamp_for_filename(driver)
    base_dir = "/home/pi/Desktop/Finale_Alva/Alva_Net"
    os.makedirs(base_dir, exist_ok=True)
    CSV_PATH_IG = f"{base_dir}/Instagram_Results_{ts}.csv"
    CSV_PATH_FB = f"{base_dir}/Facebook_Results_{ts}.csv"

    for path in [CSV_PATH_IG, CSV_PATH_FB]:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["App", "Red", "Type of test", "Latitude", "Longitude",
                             "Start time", "End time", "Status"])

def guardar_resultado(app_name, metric_type, red, lat, lon, inicio, fin, estado):
    if "Instagram" in app_name:
        path = CSV_PATH_IG
    else:
        path = CSV_PATH_FB
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([app_name, red, metric_type, lat, lon, inicio, fin, estado])
    print(f"[CSV] {app_name} | {metric_type} | {estado} ({inicio} -> {fin})")

def tomar_screenshot(driver):
    raw = driver.get_screenshot_as_png()
    return Image.open(BytesIO(raw)).convert("RGB")

def obtener_conectividad(driver):
    try:
        salida = driver.execute_script("mobile: shell", {
            "command": "dumpsys", "args": ["connectivity"], "timeout": 5000, "includeStderr": True
        }).get("stdout", "")
        if "type: WIFI" in salida: return "WiFi"
        if "type: MOBILE" in salida: return "Mobile"
    except:
        pass
    return "Disconnected"

def get_location(udid):
    try:
        output = subprocess.check_output(
            ["adb", "-s", udid, "shell", "dumpsys", "location"],
            encoding="utf-8", errors="ignore"
        )
        match = re.search(r'gps:\s+Location\[gps\s+([-\d\.]+),\s*([-\d\.]+)', output, re.I)
        if match:
            return str(match.group(1)), str(match.group(2))
    except Exception as e:
        print(f"Error obteniendo ubicación real: {e}")
    return "n/a", "n/a"

def cerrar_todas_pestanas(driver, confirm=True, timeout=7):
    try:
        print("[INFO] Cerrando pestañas abiertas...")
        wait = WebDriverWait(driver, timeout)
        wait.until(EC.presence_of_element_located((By.ID, "org.oyealva.stable:id/footer_button4"))).click()
        time.sleep(0.3)
        wait.until(EC.presence_of_element_located((By.ID, "org.oyealva.stable:id/menu_button"))).click()
        time.sleep(0.3)

        try:
            wait.until(EC.presence_of_element_located((
                By.ANDROID_UIAUTOMATOR,
                'new UiSelector().textMatches("CERRAR PESTAÑAS|Close all tabs|Cerrar pestañas|CERRAR PESTANAS")'
            ))).click()
            time.sleep(0.3)
        except Exception as e:
            print(f"[INFO] Texto de 'Cerrar pestañas' no encontrado: {e}")
            # botón por ID directo
            try:
                wait.until(EC.presence_of_element_located((By.ID, "org.oyealva.stable:id/closeAllTabs"))).click()
                time.sleep(0.3)
            except Exception as e2:
                print(f"[INFO] Botón por ID 'closeAllTabs' no disponible: {e2}")

        if confirm:
            # Acción adicional que pediste: pulsar el id toolbar_action_button
            try:
                wait.until(EC.presence_of_element_located((By.ID, "org.oyealva.stable:id/toolbar_action_button"))).click()
            except Exception as e:
                print(f"[INFO] No se pudo pulsar 'toolbar_action_button': {e}")

        # Intentar botón final (por si aparece un diálogo de confirmación)
        try:
            wait.until(EC.presence_of_element_located((
                By.ANDROID_UIAUTOMATOR,
                'new UiSelector().textMatches("ACEPTAR|Aceptar|OK|Ok|Yes|SÍ|SI")'
            ))).click()
        except Exception:
            print("[INFO] No se pudo pulsar el botón final.")

        print("[INFO] Pestañas cerradas correctamente.")
        return True

    except Exception as e:
        print(f"[ADVERTENCIA] No se pudieron cerrar pestañas: {e}")
        return False

def cerrar_solo_app(driver, package_name=BROWSER_PACKAGE):
    try:
        ok = driver.terminate_app(package_name)
        if ok:
            print(f"[INFO] App terminada con driver.terminate_app('{package_name}').")
            return True
    except Exception as e:
        print(f"[ADVERTENCIA] terminate_app falló: {e}")

    try:
        subprocess.check_output(
            ["adb", "-s", UDID, "shell", "am", "force-stop", package_name],
            encoding="utf-8", errors="ignore", timeout=5
        )
        print(f"[INFO] force-stop ejecutado para {package_name}.")
        return True
    except Exception as e:
        print(f"[ERROR] No se pudo cerrar la app con ADB: {e}")
        return False

# ========== OCR MULTIFRAME ==========
def _ocr_text(img: Image.Image) -> str:
    try:
        txt = pytesseract.image_to_string(img, lang="eng+spa").strip()
        return txt
    except Exception as e:
        print(f"[OCR] Error: {e}")
        return ""

def recortar_regiones_relevantes(img: Image.Image):
    W, H = img.size
    # regiones simples (top 60%, centro 60%, bottom 60%)
    top = img.crop((0, 0, W, int(0.33 * H)))
    mid = img.crop((0, int(0.33 * H), W, int(0.66 * H)))
    bot = img.crop((0, int(0.66 * H), W, H))
    return [top, mid, bot]

def texto_contiene_cualquiera(texto, palabras):
    t = texto.lower()
    for p in palabras:
        if p.lower() in t:
            return True
    return False

def logos_detectados(texto, logos):
    return texto_contiene_cualquiera(texto, logos)

def esperar_contenido_ocr(driver, palabras_clave, logos, timeout=10):
    """
    Devuelve (estado:str, tiempo:float)
    estado: "Successful" si encuentra palabras o logos, "Failed" si expira.
    tiempo: segundos medidos desde open_url hasta detección o timeout.
    """
    t0 = time.time()
    while True:
        img = tomar_screenshot(driver)
        # recortes
        for region in recortar_regiones_relevantes(img):
            txt = _ocr_text(region)
            if texto_contiene_cualquiera(txt, palabras_clave) or logos_detectados(txt, logos):
                dt = time.time() - t0
                print(f"[OCR] Contenido detectado en {dt:.2f} s")
                return "Successful", dt
        if time.time() - t0 > timeout:
            print(f"[OCR] Timeout {timeout}s sin detectar contenido.")
            return "Failed", timeout
        time.sleep(0.4)

# ========== APP / DRIVER ==========
def detectar_activity(pkg):
    try:
        out = subprocess.check_output(
            ["adb", "-s", UDID, "shell", "cmd", "package", "resolve-activity",
             "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER", pkg],
            encoding="utf-8", errors="ignore"
        )
        m = re.search(r'name=([\S]+)', out)
        if m:
            return m.group(1).split("/")[-1]
    except:
        pass
    return ""

def setup_driver():
    caps["appActivity"] = detectar_activity(BROWSER_PACKAGE)
    try:
        return webdriver.Remote("http://127.0.0.1:4783", options=UiAutomator2Options().load_capabilities(caps))
    except Exception as e:
        print(f"[Appium] Error: {e}")
        return None

def open_url(driver, url):
    try:
        driver.execute_script("mobile: shell", {
            'command': 'am',
            'args': ['start', '-a', 'android.intent.action.VIEW', '-d', url, '-p', BROWSER_PACKAGE],
            'includeStderr': True, 'timeout': 10000
        })
    except Exception as e:
        print(f"[Intent] Error: {e}")

# ========== TESTS ==========
def test_ig_fb(driver, app_name, url, metric_type, palabras_clave, logos):
    print(f"\n[TEST] {app_name} - {metric_type}")
    time.sleep(4)
    if not driver:
        print("[ERROR] Driver no inicializado.")
        return
    red = obtener_conectividad(driver)
    lat, lon = get_location(UDID)
    inicio = device_timestamp_str(driver)
    open_url(driver, url)
    estado, tiempo = esperar_contenido_ocr(driver, palabras_clave, logos, timeout=get_limite(metric_type))
    if estado == "Successful" and tiempo > get_limite(metric_type):
        estado = "Failed"
    fin = device_timestamp_str(driver)
    guardar_resultado(app_name, metric_type, red, lat, lon, inicio, fin, estado)

# ========== MAIN ==========
def ejecutar_pruebas(n=1, cerrar_al_final=True):
    driver = setup_driver()
    if not driver:
        return

    inicializar_csv(driver)

    try:
        for i in range(n):
            if detener:
                break
            print(f"\n[ITERACION {i+1}]")

            test_ig_fb(driver, "Instagram Web", "https://www.instagram.com/", METRICAS["FEED"],
                       ["Instagram", "tu historia", "Me gusta", "fcbarcelona", "Seguir"], ["instagram"])

            test_ig_fb(driver, "Instagram Web", "https://www.instagram.com/reels/", METRICAS["RVIDEO"],
                       ["Seguir", "Audio"], ["instagram"])

            test_ig_fb(driver, "Facebook Web", "https://m.facebook.com/", METRICAS["FEED"],
                       ["Facebook", "What on your mind?", "¿Qué estás pensando?"], ["facebook"])

            test_ig_fb(driver, "Facebook Web", "https://m.facebook.com/reel/", METRICAS["RVIDEO"],
                       ["Reels", "Tap to unmute", "Follow", "Seguir"], ["facebook"])

            cerrar_todas_pestanas(driver, confirm=True)
            time.sleep(3)

    finally:
        time.sleep(1.0)
        if cerrar_al_final:
            cerrar_solo_app(driver, BROWSER_PACKAGE)
        try:
            driver.quit()
        except:
            pass
        print("[INFO] Ejecución finalizada. App cerrada y driver liberado.")

if __name__ == "__main__":
    iniciar_logs(
        udid=UDID,
        server_url="http://127.0.0.1:4783",
        start_data_sequence=False,
        background_after=True,
        caps_overrides={"systemPort": 8241, "mjpegServerPort": 7816}
    )
    ejecutar_pruebas(n=1000, cerrar_al_final=True)
