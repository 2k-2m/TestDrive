# --- IMPORTS & CONFIGURACIÓN INICIAL ---
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import time, csv, random, os
import subprocess

# --- CONSTANTES ---
METRICAS = {
    "FEED": "Feed loading",
    "POST": "Post upload",
    "RVIDEO": "Short video playback",
    "TEXT": "Message sending",
    "PHOTO": "Image sending",
    "VIDEO": "Video sending"
}
PHOTO_THUMBNAIL_LOCATORS = [
    (AppiumBy.XPATH, '//android.widget.GridView[@resource-id="com.instagram.android:id/media_picker_grid_view"]//android.widget.Button'),
    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().resourceId("com.instagram.android:id/media_picker_grid_view").childSelector(new UiSelector().className("android.widget.Button"))'),
    (AppiumBy.CLASS_NAME, "android.widget.Button"),
]
timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
CSV_PATH = f"/media/pi/V/Instagram_Data_{timestamp}.csv"

# --- FUNCIONES DE UTILIDAD ---
def timestamp(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def guardar_resultado(tipo_test, red, lat, lon, inicio, fin, estado="Successful", falla="", tam=""):
    encabezado = [
        "App", "Red", "Type of test", "Latitude", "Longitude",
        "Initial Time", "Final Time", "State", "Cause of failure", "Content size (MB)"
    ]
    existe = os.path.isfile(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=',')
        if not existe or os.path.getsize(CSV_PATH) == 0:
            w.writerow(encabezado)
        w.writerow(["Instagram", red, tipo_test, lat, lon, inicio, fin, estado, falla, tam])

def obtener_conectividad(driver):
    try:
        salida = driver.execute_script("mobile: shell", {
            'command': 'dumpsys connectivity',
            'args': [], 'includeStderr': True, 'timeout': 5000
        })['stdout']
        if "type: WIFI" in salida: return "WiFi"
        if "type: MOBILE" in salida: return "Mobile"
    except: pass
    return "Disconnected"

def get_location(driver):
    try:
        loc = driver.location
        return str(loc['latitude']), str(loc['longitude']) if loc else ("", "")
    except: return ("", "")
    
def cerrar_apps(paquetes, udid):
    for paquete in paquetes:
        subprocess.run(['adb', '-s', udid, 'shell', 'am', 'force-stop', paquete])
        print(f"App {paquete} cerrada en {udid}.")

def esperar(driver, cond, timeout=30):
    return WebDriverWait(driver, timeout).until(cond)

def clic(driver, rid, desc="", timeout=8, mandatory=True):
    try:
        print(f"Intentando clic en: {desc} ({rid})")
        b = esperar(driver, EC.element_to_be_clickable((AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().resourceId("{rid}").enabled(true)')), timeout)
        b.click(); time.sleep(0.5)
        print(f"Clic exitoso en: {desc}")
        return True
    except Exception as e:
        print(f"Clic fallido en {desc}: {e}")
        if mandatory: raise
        return False

def ingresar_texto(driver, rid, texto, desc="", timeout=10):
    try:
        campo = esperar(driver, EC.presence_of_element_located((AppiumBy.ID, rid)), timeout)
        campo.clear(); campo.send_keys(texto); time.sleep(0.5)
        return True
    except: return False

def seleccionar_media_publicacion(driver):
    index = random.randint(0, 3)
    try:
        el = esperar(driver, EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR,
            f'new UiSelector().resourceId("com.instagram.android:id/media_picker_grid_view")'
            f'.childSelector(new UiSelector().className("android.widget.Button").instance({index}))')))
        el.click(); time.sleep(0.7)
        tam_archivo = "2.3"#obtener_tamano_archivo_android(ARCHIVOS_CONOCIDOS[index])
        return True, tam_archivo
    except:
        return False, "Desconocido"

def seleccionar_media(driver, index):
    try:
        sel = esperar(driver, EC.presence_of_element_located((
            AppiumBy.ANDROID_UIAUTOMATOR,
            f'new UiSelector().resourceId("com.instagram.android:id/gallery_grid").childSelector(new UiSelector().className("android.widget.CheckBox").instance({index}))')))
        sel.click(); time.sleep(.7)
        return True
    except: return False

def compartir_P(driver, tipo_metrica, red, lat, lon, inicio, tam_archivo, wait_for_id, wait_for_id2, wait_timeout=25):
    try:
        WebDriverWait(driver, wait_timeout).until(lambda d: (
            # Condición 1: desapareció el contenedor
            not d.find_elements(AppiumBy.ID, wait_for_id)
            # Condición 2: apareció el botón "Enviar"
            or d.find_elements(AppiumBy.ID, wait_for_id2)
        ))
        print("Publicación detectada como completada (desapareció el contenedor o apareció el botón Enviar).")
        guardar_resultado(tipo_metrica, red, lat, lon, inicio, timestamp(), "Successful", tam=tam_archivo)
    except TimeoutException:
        print("Timeout: no se detectó desaparición ni aparición del botón Enviar.")
        guardar_resultado(tipo_metrica, red, lat, lon, inicio, timestamp(), "Failed", "Timeout", tam_archivo)

def compartir(driver, tipo_metrica, red, lat, lon, inicio, tam_archivo, wait_for_id, wait_timeout=8):
    try:
        WebDriverWait(driver, wait_timeout).until(
            EC.invisibility_of_element_located((AppiumBy.ID, wait_for_id))
        )
        guardar_resultado(tipo_metrica, red, lat, lon, inicio, timestamp(), "Successful", tam=tam_archivo)
    except TimeoutException:
        guardar_resultado(tipo_metrica, red, lat, lon, inicio, timestamp(), "Failed", "Timeout", tam_archivo)

def click_button(driver, resource_id, description="", timeout=10, mandatory=True):
    try:
        button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((AppiumBy.ID, resource_id))
        )
        button.click()
        time.sleep(0.5)
        return True
    except Exception:
        if mandatory: raise
        return False

def enviar_contenido_F(driver, tipo, index, btn_id, wait_for_id):
    if not clic(driver, "com.instagram.android:id/row_thread_composer_button_gallery", "Botón Galería"):
        return
    
    clic(driver, "com.instagram.android:id/media_picker_header_title_container")
    el = esperar(driver, EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR,
            f'new UiSelector().resourceId("com.instagram.android:id/album_thumbnail_recycler_view")'
            f'.childSelector(new UiSelector().description("DriveTest"))')))
    el.click()

    if not seleccionar_media(driver, index):
        guardar_resultado(tipo, red, "", "", "", "", "Failed", "Item no found", tam_archivo)
        return
    lat, lon = get_location(driver)
    inicio = timestamp()
    tam_archivo = "2.3"#obtener_tamano_archivo_android(ARCHIVOS_CONOCIDOS[index])
    if click_button(driver, btn_id, "Enviar foto", False, 7):
        compartir(driver, tipo, red, lat, lon, inicio, tam_archivo, wait_for_id)
    else:
        guardar_resultado(tipo, red, lat, lon, inicio, timestamp(), "Failed", "No se encontró botón", tam_archivo)

def enviar_contenido_V(driver, tipo, index, btn_id, wait_for_id):
    if not clic(driver, "com.instagram.android:id/row_thread_composer_button_gallery", "Botón Galería"):
        return
    
    clic(driver, "com.instagram.android:id/media_picker_header_title_container")
    el = esperar(driver, EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR,
            f'new UiSelector().resourceId("com.instagram.android:id/album_thumbnail_recycler_view")'
            f'.childSelector(new UiSelector().description("DriveTest"))')))
    el.click()

    if not seleccionar_media(driver, index):
        guardar_resultado(tipo, red, "", "", "", "", "Failed", "Item no found", tam_archivo)
        return
    lat, lon = get_location(driver)
    inicio = timestamp()
    tam_archivo = "20"#obtener_tamano_archivo_android(ARCHIVOS_CONOCIDOS[index])
    if click_button(driver, btn_id, "Enviar video", False, 7):
        time.sleep(2)
        compartir(driver, tipo, red, lat, lon, inicio, tam_archivo, wait_for_id, 45)
    else:
        guardar_resultado(tipo, red, lat, lon, inicio, timestamp(), "Failed", "No se encontró botón", tam_archivo)

def click_tab_icon(driver, resource_id, instance_index=0, description="", timeout=15, mandatory=True):
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((AppiumBy.ANDROID_UIAUTOMATOR,
            f'new UiSelector().resourceId("{resource_id}").instance({instance_index}).enabled(true)')))
        element.click(); time.sleep(0.5)
        return True
    except:
        if mandatory: raise
        return False

def enviar_mensaje_texto(driver, mensaje, red):
    tam_archivo = f"{len(mensaje)}C"
    if ingresar_texto(driver, "com.instagram.android:id/row_thread_composer_edittext", mensaje):
        lat, lon = get_location(driver)
        inicio = timestamp()
        if clic(driver, "com.instagram.android:id/row_thread_composer_send_button_container", "Enviar texto", timeout=7, mandatory=False):
            compartir(driver, METRICAS["TEXT"], red, lat, lon, inicio, tam_archivo, "com.instagram.android:id/action_icon")
        else:
            guardar_resultado(METRICAS["TEXT"], red, lat, lon, inicio, timestamp(), "Failed", "No se encontró botón", tam=tam_archivo)
    else:
        guardar_resultado(METRICAS["TEXT"], red, "", "", "", "", "Failed", "No se encontró campo de texto", tam=tam_archivo)

def asegurar_publicacion_activa(driver, timeout=5):
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/cam_dest_feed"))
        ).click(); return True
    except:
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "REEL"))
            ).click()
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/cam_dest_feed"))
            ).click(); return True
        except: return False

def buscar_reel_con_scrubber(driver, intentos_maximos=5):
    for _ in range(intentos_maximos):
        try:
            driver.find_element(AppiumBy.ID, "com.instagram.android:id/scrubber")
            return True
        except:
            driver.swipe(500, 1600, 500, 400, 500); time.sleep(2)
    return False

def verificar_reproduccion_video(driver, duracion_segundos=15, check_interval=5):
    tiempo_total = 0
    progreso_anterior = -1
    intentos_sin_scrubber = 0
    while tiempo_total < duracion_segundos:
        try:
            scrubber = driver.find_element(AppiumBy.ID, "com.instagram.android:id/scrubber")
            progreso_actual = float(scrubber.get_attribute("text"))
            if progreso_actual == progreso_anterior:
                return False
            progreso_anterior = progreso_actual
            intentos_sin_scrubber = 0
        except:
            intentos_sin_scrubber += 1
            if intentos_sin_scrubber >= 3: return False
        time.sleep(check_interval)
        tiempo_total += check_interval
    return True

def obtener_tamano_archivo_android(nombre_archivo):
    ruta = f"/sdcard/DriveTest/{nombre_archivo}"  # ✅ Carpeta correcta
    output = os.popen(f"adb shell ls -l {ruta}").read()
    try:
        peso_bytes = int(output.split()[4])
        peso_mb = round(peso_bytes / (1024 * 1024), 2)
        return f"{peso_mb}"
    except:
        return "Desconocido"

# --- DRIVER SETUP ---
udid = "R58M795NHZF"
def setup_driver():
    caps = {
        "platformName": "Android",
        "deviceName": "R58M795NHZF",
        "udid": "R58M795NHZF",
        "appPackage": "com.instagram.android",
        "appActivity": "com.instagram.android.activity.MainTabActivity",
        "automationName": "UiAutomator2",
        "forceAppLaunch": True,
        "systemPort": 8200, 
        "noReset": True,
        
        "newCommandTimeout": 360
    }
    try:
        return webdriver.Remote("http://127.0.0.1:4723", options=UiAutomator2Options().load_capabilities(caps))
    except Exception as e:
        print(f"No se pudo iniciar Appium: {e}")
        return None

# --- PRUEBA PRINCIPAL ---
def test_instagram():
    print("Iniciando prueba Instagram...")
    global red
    driver = setup_driver()
    if not driver:
        return
    red = obtener_conectividad(driver)

    # --- Carga de Feed ---
    print("Cargando feed...")
    lat, lon = get_location(driver)
    inicio = timestamp()
    try:
        esperar(driver, EC.any_of(
            EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/recycler_view")),
            EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/refreshable_container"))
        ), 15)
        guardar_resultado(METRICAS["FEED"], red, lat, lon, inicio, timestamp())
    except:
        guardar_resultado(METRICAS["FEED"], red, lat, lon, inicio, timestamp(), "Failed", "Timeout")
    print("Cargando feed...OK")

    # --- Publicación Imagen ---
    print("Publicando imagen...")
    if click_tab_icon(driver, "com.instagram.android:id/tab_icon", 3, "Crear", 10) and asegurar_publicacion_activa(driver):
        clic(driver, "com.instagram.android:id/gallery_folder_menu_tv")
        el = esperar(driver, EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR,
            f'new UiSelector().resourceId("com.instagram.android:id/album_thumbnail_recycler_view")'
            f'.childSelector(new UiSelector().description("DriveTest"))')))
        el.click()
        exito, tam_archivo = seleccionar_media_publicacion(driver)
        if exito:
            clic(driver, "com.instagram.android:id/next_button_textview")
            clic(driver, "com.instagram.android:id/creation_next_button")
            lat, lon = get_location(driver)
            inicio = timestamp()
            if clic(driver, "com.instagram.android:id/share_footer_button", "Compartir"):
                compartir_P(driver, METRICAS["POST"], red, lat, lon, inicio, tam_archivo, 
                            "com.instagram.android:id/row_pending_container", 
                            "com.instagram.android:id/row_pending_media_reshare_button", 25)
    print("Publicando imagen...OK")

    # --- Reels ---
    print("Reproduciendo Reel...")
    click_tab_icon(driver, "com.instagram.android:id/tab_icon", 4, "Reels", 15)
    if buscar_reel_con_scrubber(driver):
        lat, lon = get_location(driver)
        inicio = timestamp()
        if verificar_reproduccion_video(driver):
            guardar_resultado(METRICAS["RVIDEO"], red, lat, lon, inicio, timestamp(), "Successful", "", "0.0")
        else:
            guardar_resultado(METRICAS["RVIDEO"], red, lat, lon, inicio, timestamp(), "Failed", "Reel no válido", "0.0")
    print("Reproduciendo Reel...OK")

    # --- Enviar mensaje de texto ---
    print("Enviando mensaje de texto...")
    try:
        click_tab_icon(driver, "com.instagram.android:id/tab_icon", 0, "Home", 7)
        clic(driver, "com.instagram.android:id/action_bar_inbox_button", "Inbox", 5)
        clic(driver, "com.instagram.android:id/row_inbox_container", "Primer chat", 5)
        mensaje = "Hola Mundo Peru"
        tam_archivo = f"{len(mensaje)}C"
        if ingresar_texto(driver, "com.instagram.android:id/row_thread_composer_edittext", mensaje, "Campo texto"):
            lat, lon = get_location(driver)
            inicio = timestamp()
            if clic(driver, "com.instagram.android:id/row_thread_composer_send_button_container", "Botón enviar", 7, False):
                compartir(driver, METRICAS["TEXT"], red, lat, lon, inicio, tam_archivo, "com.instagram.android:id/action_icon")
            else:
                guardar_resultado(METRICAS["TEXT"], red, lat, lon, inicio, timestamp(), "Failed", "Botón enviar no disponible", tam_archivo)
        else:
            guardar_resultado(METRICAS["TEXT"], red, "", "", "", "", "Failed", "Campo texto no encontrado", tam_archivo)
    except Exception as e:
        guardar_resultado(METRICAS["TEXT"], red, "", "", "", "", "Failed", resumir_error(e), tam_archivo)
    print("Enviando mensaje de texto...OK")

    # --- Enviar imagen por mensaje ---
    print("Enviando imagen por mensaje...")
    try:
        enviar_contenido_F(driver, METRICAS["PHOTO"], 1, "com.instagram.android:id/direct_media_send_button", "com.instagram.android:id/action_icon")
    except Exception as e:
        guardar_resultado(METRICAS["PHOTO"], red, "", "", timestamp(), timestamp(), "Failed", resumir_error(e), "Desconocido")
    print("Enviando imagen por mensaje...OK")

    # --- Enviar video por mensaje ---
    print("Enviando video por mensaje...")
    try:
        enviar_contenido_V(driver, METRICAS["VIDEO"], 5, "com.instagram.android:id/direct_media_send_button", "com.instagram.android:id/action_icon")
    except Exception as e:
        guardar_resultado(METRICAS["VIDEO"], red, "", "", timestamp(), timestamp(), "Failed", resumir_error(e), "Desconocido")
    print("Enviando video por mensaje...OK")

    # Final
    cerrar_apps(["com.instagram.android"], udid)
    driver.quit()
    time.sleep(2)

# ---Funciones para el main ---
def inicializar_csv():
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "App", "Red", "Type of test", "Latitude", "Longitude",
                "Initial Time", "Final time", "State", "Cause of failure", "Content size (MB)"
            ])

def ejecutar_pruebas(n=1):
    for i in range(n):
        print(f"\n Iteración {i+1}")
        try:
            test_instagram()
        except Exception as e:
            print(f" Error en la iteración {i+1}: {e}")

def generar_vector_archivos(carpeta="/sdcard/DriveTest"):
    salida = subprocess.getoutput(f'adb shell ls -ltlh {carpeta}')
    archivos_conocidos = []

    for linea in salida.strip().split('\n'):
        columnas = linea.split()
        if len(columnas) >= 9:
            nombre_archivo = ' '.join(columnas[8:])
            if "." in nombre_archivo and not nombre_archivo.endswith("/"):
                archivos_conocidos.append(nombre_archivo)

    return archivos_conocidos

ARCHIVOS_CONOCIDOS = ['1Imagen.jpg', '2Imagen.jpg', '3Imagen.jpg', '4Imagen.jpg', 'Video2.mp4', 'Video.mp4']

def resumir_error(e):
    mensaje = str(e)
    if "ECONNREFUSED" in mensaje:
        return "Appium error"
    elif "socket hang up" in mensaje:
        return "Conecction lost"
    elif "NoSuchElement" in mensaje or "could not be located" in mensaje:
        return "Item no found"
    else:
        return "Unexpected error"

#generar_vector_archivos()

# --- EJECUCIÓN ---
if __name__ == "__main__":
    inicializar_csv()
    ejecutar_pruebas(1000)
    
