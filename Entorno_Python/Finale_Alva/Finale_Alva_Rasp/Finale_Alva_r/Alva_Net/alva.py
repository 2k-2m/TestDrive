# -*- coding: utf-8 -*-
from appium import webdriver
from appium.options.android import UiAutomator2Options
from datetime import datetime
from io import BytesIO
from PIL import Image
import pytesseract
import time, csv, os, subprocess, re, signal, shutil

# Selenium (esperas explícitas)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --------- Tesseract (auto) ----------
pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract") or "/usr/bin/tesseract"

# ========== CONFIGURACION INICIAL ==========
# Señal y bandera de parada (graceful)
detener = False
def manejar_senal(sig, frame):
    global detener
    print("\n[INFO] Señal de terminación recibida. El script se detendrá después de la iteración actual...")
    detener = True
signal.signal(signal.SIGTERM, manejar_senal)
signal.signal(signal.SIGINT, manejar_senal)

METRICAS = {"FEED": "Feed loading", "RVIDEO": "Short video playback"}
timestamp_str = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
CSV_PATH = f"/home/pi/Desktop/Finale_Alva/Nativo/Social_Web_{timestamp_str}.csv"

BROWSER_PACKAGE = os.getenv("ALVA_PKG", "org.oyealva.stable")
UDID = os.getenv("UDID", "R58M795NHZF")

caps = {
    "platformName": "Android",
    "deviceName": UDID,
    "udid": UDID,
    "automationName": "UiAutomator2",
    "appPackage": BROWSER_PACKAGE,
    "forceAppLaunch": True,
    "systemPort": 8230,          # distinto a otros
    "noReset": True,
    "newCommandTimeout": 360
}

# ========== UTILIDADES ==========
def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def inicializar_csv():
    global CSV_PATH_IG, CSV_PATH_FB
    date_str = datetime.now().strftime("%Y_%m_%d")
    CSV_PATH_IG = f"/home/pi/Desktop/Finale_Alva/Nativo/Instagram_Results_{date_str}.csv"
    CSV_PATH_FB = f"/home/pi/Desktop/Finale_Alva/Nativo/Facebook_Results_{date_str}.csv"

    for path in [CSV_PATH_IG, CSV_PATH_FB]:
        if not os.path.exists(path):
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "App", "Red", "Type of test", "Latitude", "Longitude",
                    "Initial Time", "Final Time", "State", "Cause of failure", "Content size (MB)"
                ])

def guardar_resultado(app, tipo_test, red, lat, lon, inicio, fin, estado="Successful", falla="", tam=""):
    if "Duración" in falla and estado == "Successful":
        falla = ""
    app_simple = "Instagram" if "Instagram" in app else "Facebook"
    path = CSV_PATH_IG if app_simple == "Instagram" else CSV_PATH_FB
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([app_simple, red, tipo_test, lat, lon, inicio, fin, estado, falla, tam])

def obtener_conectividad(driver):
    try:
        salida = driver.execute_script("mobile: shell", {
            'command': 'dumpsys connectivity',
            'args': [], 'includeStderr': True, 'timeout': 5000
        })['stdout']
        if "type: WIFI" in salida: return "WiFi"
        if "type: MOBILE" in salida: return "Mobile"
    except:
        pass
    return "Disconnected"

def get_location(udid):
    try:
        output = subprocess.check_output(
            ["adb", "-s", udid, "shell", "dumpsys", "location"],
            encoding="utf-8"
        )
        match = re.search(r'gps:\s+Location\[gps\s+([-\d\.]+),\s*([-\d\.]+)', output, re.I)
        if match:
            return str(match.group(1)), str(match.group(2))
    except Exception as e:
        print(f"Error obteniendo ubicación real: {e}")
    return "n/a", "n/a"

# ---- Cerrar SOLAMENTE pestañas, sin cerrar la app ----
def cerrar_todas_pestanas(driver, confirm=True, timeout=7):
    try:
        print("[INFO] Cerrando pestañas abiertas (fin de iteración)...")
        wait = WebDriverWait(driver, timeout)

        # 1) Conmutador de pestañas
        wait.until(EC.presence_of_element_located((By.ID, "org.oyealva.stable:id/footer_button4"))).click()
        time.sleep(0.3)

        # 2) Abrir menú
        wait.until(EC.presence_of_element_located((By.ID, "org.oyealva.stable:id/menu_button"))).click()
        time.sleep(0.3)

        # 3) Elegir "Cerrar todas las pestañas" (es/en)
        try:
            wait.until(EC.presence_of_element_located((
                By.XPATH,
                '//android.widget.TextView[@resource-id="org.oyealva.stable:id/menu_item_text" and '
                '(@text="Cerrar todas las pestañas" or @text="Close all tabs")]'
            ))).click()
        except Exception:
            driver.find_element(
                By.XPATH,
                '//android.widget.TextView[contains(@text,"Cerrar todas")]'
            ).click()

        time.sleep(0.2)

        # 4) Confirmación del diálogo
        if confirm:
            try:
                wait.until(EC.element_to_be_clickable((By.ID, "org.oyealva.stable:id/positive_button"))).click()
            except Exception:
                print("[INFO] No apareció diálogo de confirmación (continuando).")

        print("[INFO] Pestañas cerradas correctamente.")
        return True
    except Exception as e:
        print(f"[ADVERTENCIA] No se pudieron cerrar pestañas: {e}")
        return False

# ---- Cerrar vía "Recents" (App Switch) y Clear All (Samsung) ----
def cerrar_via_recientes(driver, timeout=6):
    """
    Abre la vista de apps recientes (KEYCODE 187) y toca el botón 'Clear all'
    específico de Samsung Launcher: com.sec.android.app.launcher:id/clear_all
    """
    try:
        # 1) Abrir "Recents" (KEYCODE_APP_SWITCH = 187)
        try:
            driver.press_keycode(187)
        except Exception:
            driver.execute_script("mobile: shell", {
                'command': 'input', 'args': ['keyevent', '187'],
                'includeStderr': True, 'timeout': 3000
            })

        # 2) Tocar el botón "Clear all" del launcher de Samsung
        wait = WebDriverWait(driver, timeout)
        clear_btn = wait.until(EC.element_to_be_clickable(
            (By.ID, "com.sec.android.app.launcher:id/clear_all")
        ))
        clear_btn.click()
        print("[INFO] 'Clear all' (Samsung) pulsado para cerrar las apps recientes.")
        time.sleep(0.6)
        return True
    except Exception as e:
        print(f"[ADVERTENCIA] No se pudo pulsar 'Clear all' en Recents: {e}")
        return False

# ========== OCR MULTIFRAME ==========
def esperar_contenido_ocr(driver, palabras_clave, logos_unicos, timeout=7):
    start_time = time.time()
    while True:
        if detener:
            print("[INFO] Proceso detenido por el usuario durante OCR.")
            return "Failed", round(time.time() - start_time, 2)
        elapsed = time.time() - start_time
        if elapsed > timeout:
            return "Failed", round(timeout, 2)
        try:
            png = driver.get_screenshot_as_png()
            img = Image.open(BytesIO(png))
            texto = pytesseract.image_to_string(img).lower()
            print(f"[OCR] ({elapsed:.2f}s): {texto}")
            hay_contenido = any(p.lower() in texto for p in palabras_clave)
            _solo_logo = any(p.lower() in texto for p in logos_unicos) and not hay_contenido
            if hay_contenido:
                return "Successful", round(elapsed, 2)
        except Exception as e:
            print(f"[OCR] Error: {e}")
        # espera cooperativa corta
        for _ in range(5):
            if detener: 
                print("[INFO] Proceso detenido por el usuario durante OCR-sleep.")
                return "Failed", round(time.time()-start_time, 2)
            time.sleep(0.2)

# ========== DRIVER ==========
def detectar_activity(pkg):
    try:
        out = subprocess.check_output(
            ["adb", "-s", UDID, "shell", "cmd", "package", "resolve-activity",
             "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER", pkg],
            encoding="utf-8"
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
    if detener:
        print("[INFO] Proceso detenido por el usuario antes del test.")
        return
    print(f"\n[TEST] {app_name} - {metric_type}")
    if not driver:
        print("[ERROR] Driver no inicializado.")
        return
    red = obtener_conectividad(driver)
    lat, lon = get_location(UDID)
    inicio = timestamp()
    open_url(driver, url)
    estado, tiempo = esperar_contenido_ocr(driver, palabras_clave, logos)
    fin = timestamp()
    guardar_resultado(app_name, metric_type, red, lat, lon, inicio, fin, estado)
    # Nota: cierre de pestañas/recents al final de cada iteración en ejecutar_pruebas()

# ========== MAIN ==========
def ejecutar_pruebas(n=1, cerrar_al_final=True):
    """
    n: número de iteraciones (cada iteración ejecuta todos los tests).
    cerrar_al_final: si True, cierra la app y el driver al terminar TODAS las iteraciones.
    """
    driver = setup_driver()
    if not driver:
        return

    cerro_en_ultima_iteracion = False

    try:
        for i in range(n):
            if detener:
                print("[INFO] Proceso detenido por el usuario.")
                break
            print(f"\n[ITERACION {i+1}]")

            # ---- Tests de la iteración ----
            test_ig_fb(driver, "Instagram Web", "https://www.instagram.com/", METRICAS["FEED"],
                       ["Instagram", "tu historia", "Me gusta"], ["instagram"])
            if detener: break

            test_ig_fb(driver, "Instagram Web", "https://www.instagram.com/reels/", METRICAS["RVIDEO"],
                       ["Seguir", "Audio"], ["instagram"])
            if detener: break

            test_ig_fb(driver, "Facebook Web", "https://m.facebook.com/", METRICAS["FEED"],
                       ["Facebook", "What on your mind?", "¿Qué estás pensando?"], ["facebook"])
            if detener: break

            test_ig_fb(driver, "Facebook Web", "https://m.facebook.com/reel/", METRICAS["RVIDEO"],
                       ["Reels", "Tap to unmute", "Follow", "Seguir"], ["facebook"])
            if detener: break

            # ---- Cierre al FINAL de la iteración (UNA sola vez) ----
            _tabs_ok = cerrar_todas_pestanas(driver, confirm=True)
            _rec_ok  = cerrar_via_recientes(driver)
            cerro_en_ultima_iteracion = (_tabs_ok or _rec_ok)

            # pequeña espera cooperativa
            for _ in range(10):
                if detener:
                    print("[INFO] Proceso detenido por el usuario al finalizar iteración.")
                    break
                time.sleep(0.1)
            if detener: break

    finally:
        if cerrar_al_final:
            # Si la última iteración no logró cerrar “bonito”, intenta un backup
            if not cerro_en_ultima_iteracion:
                try:
                    cerrar_via_recientes(driver)
                except Exception:
                    pass
            try:
                driver.quit()
            except Exception as e:
                print(f"[WARN] driver.quit() falló: {e}")
            print("[INFO] Ejecución finalizada. App cerrada y driver liberado.")

if __name__ == "__main__":
    inicializar_csv()
    ejecutar_pruebas(n=1000, cerrar_al_final=True)

