# -*- coding: utf-8 -*-
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import time, csv, signal, os, subprocess, re, random

# ──────────────────────────────────────────────────────────────────────────────
# Signal Handling (Manejo de Señal para Detener el Script)
# ──────────────────────────────────────────────────────────────────────────────
detener = False
def manejar_senal(sig, frame):
    global detener
    print("\n[INFO] Señal de terminación recibida. El script se detendrá después de la iteración actual...")
    detener = True
signal.signal(signal.SIGTERM, manejar_senal)
signal.signal(signal.SIGINT, manejar_senal)

# ──────────────────────────────────────────────────────────────────────────────
# Configuration (Configuración Central)
# ──────────────────────────────────────────────────────────────────────────────
udid = "R58MA32XQQW"
app = "Facebook"
timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
archivo_csv = f"/home/pi/Desktop/Finale_Alva/Nativo/Data/Facebook_Data_{timestamp}.csv"


encabezados = [
    "App","Red","Type of test","Latitude","Longitude",
    "Initial Time","Final Time","State","Cause of failure","Content Size (MB)"
]
# Timeouts en segundos
TIMEOUT_GENERAL = 10
TIMEOUT_VIDEO = 20
TIMEOUT_WAIT_FOR_ELEMENT = 5

# ──────────────────────────────────────────────────────────────────────────────
# Funciones de Ayuda (Comunes)
# ──────────────────────────────────────────────────────────────────────────────

def escribir_fila(app, red, tipo, latitud, longitud, inicio, fin, resultado, falla, tamanio):
    fila = [app, red, tipo, latitud, longitud,
            inicio.strftime("%Y-%m-%d %H:%M:%S"),
            fin.strftime("%Y-%m-%d %H:%M:%S"),
            resultado, falla, tamanio]
    os.makedirs(os.path.dirname(archivo_csv), exist_ok=True)
    with open(archivo_csv, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=',')
        if f.tell() == 0:
            writer.writerow(encabezados)
        writer.writerow(fila)

def iniciar_app(package_name, activity_name, udid):
    comando = f"adb -s {udid} shell am start -n {package_name}/{activity_name}"
    if os.system(comando) == 0:
        print(f"App {package_name} iniciada en {udid}")
    else:
        print(f"Error al iniciar {package_name} en {udid}")

def cerrar_todas_las_apps(paquetes, udid):
    for paquete in paquetes:
        subprocess.run(['adb', '-s', udid, 'shell', 'am', 'force-stop', paquete], stdout=subprocess.DEVNULL)
    print(f"Apps {paquetes} cerradas en {udid}.")

def obtener_ubicacion(udid):
    try:
        output = subprocess.check_output(["adb", "-s", udid, "shell", "dumpsys", "location"], encoding="utf-8")
        match = re.search(r'gps:\s+Location\[gps\s+([-\d\.]+),\s*([-\d\.]+)', output, re.I)
        if match:
            return str(match.group(1)), str(match.group(2)), "n/a"
    except Exception as e:
        print(f"Error obteniendo GPS vía ADB: {e}")
    return "n/a", "n/a", "n/a"

def get_network_status(driver):
    try:
        output = driver.execute_script("mobile: shell", {
            'command': 'dumpsys', 'args': ['connectivity'], 'includeStderr': True, 'timeout': 5000
        })['stdout']
        networks = []
        for block in output.split("NetworkAgentInfo")[1:]:
            if "state: CONNECTED" in block and "VALIDATED" in block:
                if "type: WIFI" in block: networks.append("WIFI")
                elif "type: MOBILE" in block: networks.append("MOBILE")
        if "WIFI" in networks: return "WiFi"
        if "MOBILE" in networks: return "Mobile"
        return "Disconnected"
    except Exception as e:
        print(f"[WARN] No se pudo obtener el estado de la red: {e}")
        return "Disconnected"

def find_and_click(driver, by, selector, description="Elemento", timeout=TIMEOUT_WAIT_FOR_ELEMENT):
    try:
        wait = WebDriverWait(driver, timeout)
        element = wait.until(EC.element_to_be_clickable((by, selector)))
        element.click()
        print(f"[OK] {description}")
        return True
    except TimeoutException:
        print(f"[MISS] {description}")
        return False

def click_first_available_file(driver, max_attempts=5):
    for i in range(max_attempts):
        try:
            selector = f'new UiSelector().resourceId("com.android.documentsui:id/icon_thumb").instance({i})'
            element = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, selector)
            if element.get_attribute("enabled") == "true":
                element.click()
                print(f"[OK] Archivo clickeado en instancia {i}")
                return True
        except NoSuchElementException:
            pass
    print("[MISS] No se encontró ningún archivo habilitado.")
    return False

# ──────────────────────────────────────────────────────────────────────────────
# LÓGICA DE CONFIRMACIÓN DE ENVÍO (MÉTODO DEL ANCLA)
# ──────────────────────────────────────────────────────────────────────────────
XPATH_LAST_SENT = (
    '(//*[@content-desc="Sent" or @content-desc="Sent " or @content-desc="Delivered" or @content-desc="Enviado" '
    'or @text="Sent" or @text="Sent " or @text="Delivered" or @text="Enviado"])[last()]'
)
XPATH_FAIL = (
    '//*[@text="Not sent" or @content-desc="Not sent" or @text="Failed" or @content-desc="Failed" or '
    '@text="Try again" or @content-desc="Try again" or @text="No enviado" or @content-desc="No enviado" or '
    '@text="Reintentar" or @content-desc="Reintentar" or @text="Error" or @content-desc="Error"]'
)

def _get_last_sent_element(driver, retries=3):
    for attempt in range(retries):
        try:
            elements = driver.find_elements(AppiumBy.XPATH, XPATH_LAST_SENT)
            if not elements: return None, -1
            last_element = elements[-1]
            rect = last_element.rect
            return last_element.id, (rect['y'] + rect['height'])
        except Exception:
            time.sleep(0.2)
    return None, -1

def _is_fail_marker_visible(driver):
    try:
        return bool(driver.find_elements(AppiumBy.XPATH, XPATH_FAIL))
    except:
        return False

def capture_anchor(driver):
    anchor_id, anchor_bottom = _get_last_sent_element(driver)
    had_any_sent = anchor_id is not None
    print(f"[ANCHOR] Capturado: id={anchor_id}, bottom={anchor_bottom}, had_any_sent={had_any_sent}")
    return anchor_id, anchor_bottom, had_any_sent

def wait_for_send_confirmation(driver, anchor_id, anchor_bottom, had_any_sent, timeout: int, poll: float = 0.05):
    start_time = time.time()
    driver.implicitly_wait(0)
    try:
        while time.time() - start_time < timeout:
            if _is_fail_marker_visible(driver):
                return datetime.now(), "Failed", "Indicador de fallo encontrado"
            
            current_id, current_bottom = _get_last_sent_element(driver)
            
            if not had_any_sent and current_id is not None:
                return datetime.now(), "Successful", ""
            
            if current_id is not None:
                if anchor_id is not None and current_id != anchor_id:
                    return datetime.now(), "Successful", ""
                if anchor_bottom != -1 and current_bottom > anchor_bottom:
                    return datetime.now(), "Successful", ""
            time.sleep(poll)
    finally:
        driver.implicitly_wait(3)
    return datetime.now(), "Failed", "Timeout"

def click_si_existe(driver, by, selector, desc="Elemento"):
    try:
        el = driver.find_element(by, selector)
        el.click()
        print(f"{desc} clickeado.")
        return True
    except NoSuchElementException:
        print(f"{desc} no encontrado.")
        return False

# ──────────────────────────────────────────────────────────────────────────────
# Flujo Principal de Pruebas
# ──────────────────────────────────────────────────────────────────────────────
def test_login_facebook():
    desired_caps = {
        "platformName": "Android", "deviceName": "R58MA32XQQW", "udid": udid,
        "appPackage": "com.facebook.katana", "automationName": "UiAutomator2",
        "systemPort": 8201, "noReset": True
    }
    options = UiAutomator2Options().load_capabilities(desired_caps)
    
    iteracion = 0
    while not iteracion ==1: #detener:
        iteracion += 1
        driver = None
        print(f"\n--- Iteración Facebook #{iteracion} ---")
        if detener:
            print("[INFO] Proceso detenido por el usuario.")
            break
        driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
        driver.implicitly_wait(3)
        iniciar_app("com.facebook.katana", "com.facebook.katana.LoginActivity", udid)
        time.sleep(3)
        
        try:    
            ##### FEED #####
            inicio_feed = datetime.now()
            latitude_feed, longitude_feed, _ = obtener_ubicacion(udid)
            red_feed = get_network_status(driver)
            
            if red_feed == "Disconnected":
                fin_feed = datetime.now()
                resultado = "Failed"
                falla = "Item no found"
                tamanio = ""
                escribir_fila(app, red_feed, "Feed loading", latitude_feed, longitude_feed, inicio_feed, fin_feed, resultado, falla, tamanio)
            else:
                feed_elements = driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR,
                                                    'new UiSelector().className("android.view.ViewGroup").instance(16)')
                if feed_elements:
                    fin_feed = datetime.now()
                    resultado = "Successful"
                    falla = ""
                    tamanio = ""
                    print("Primer grupo del feed cargado correctamente. (instance)")
                else:
                    fin_feed = datetime.now()
                    resultado = "Failed"
                    falla = "Item no found"
                    tamanio = ""
                escribir_fila(app, red_feed, "Feed loading", latitude_feed, longitude_feed, inicio_feed, fin_feed, resultado, falla, tamanio)

                if detener:
                    print("[INFO] Proceso detenido por el usuario.")
                    break

                ######## REPRODUCCION DE VIDEO CORTO ########
                video = click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                            'new UiSelector().descriptionMatches("^Video.*")',
                            "Botón Video")
                if video == False:
                    click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                            'new UiSelector().className("android.widget.FrameLayout").instance(12)',
                            "Botón Video")
                progreso_detectado = False
                tiempo_inicio = time.time()
                red_video_corto = get_network_status(driver)
                latitude_video_corto, longitude_video_corto,_ = obtener_ubicacion(udid)
                inicio_video_corto = datetime.now()
                if red_video_corto == "Disconnected":
                    fin_video_corto = datetime.now()
                    resultado = "Failed"
                    falla = "No service"
                    tamanio = ""
                    print("Red no disponible, carga de video corto fallido.")
                else:
                    while time.time() - tiempo_inicio < 15:
                        try:
                            driver.find_element(AppiumBy.CLASS_NAME, "android.widget.ProgressBar")
                            progreso_detectado = True
                            break
                        except:
                            pass
                        time.sleep(0.1)
                    if progreso_detectado:
                        fin_video_corto = datetime.now()
                        resultado = "Failed"
                        falla = "TimeOut"
                        tamanio = ""
                        print("Video corto reproducido sin éxito (progress bar detectado)")
                    else:
                        fin_video_corto = datetime.now()
                        resultado = "Successful"
                        falla = ""
                        tamanio = ""
                        print("Video corto reproducido con éxito (sin progress bar)")
                escribir_fila(app, red_video_corto, "Short video playback", latitude_video_corto, longitude_video_corto, inicio_video_corto, fin_video_corto, resultado, falla, tamanio)
                
                if detener:
                    print("[INFO] Proceso detenido por el usuario.")
                    break
        
        except Exception as e:
            print(f"[FATAL] La iteración #{iteracion} falló catastróficamente: {e}")
        finally:
            if driver:
                cerrar_todas_las_apps(["com.facebook.katana", "com.facebook.orca"], udid)
                driver.quit()
            print("Reinicio de app en 3s...\n")
            time.sleep(3)

if __name__ == '__main__':
    test_login_facebook()
