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
ARCHIVOS_CONOCIDOS = [
    "Video.mp4",
    "Video2.mp4",
    "Imagen1.jpg",
    "Imagen2.jpg",
    "Imagen3.jpg",
    "Imagen4.jpg",
]
METRICAS = {
    "FEED": "Carga_Feed",
    "POST": "Publicacion",
    "RVIDEO": "Re_Video",
    "TEXT": "Ms_Texto",
    "PHOTO": "Ms_Foto",
    "VIDEO": "Ms_Video"
}
PHOTO_THUMBNAIL_LOCATORS = [
    (AppiumBy.XPATH, '//android.widget.GridView[@resource-id="com.instagram.android:id/media_picker_grid_view"]//android.widget.Button'),
    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().resourceId("com.instagram.android:id/media_picker_grid_view").childSelector(new UiSelector().className("android.widget.Button"))'),
    (AppiumBy.CLASS_NAME, "android.widget.Button"),
]
CSV_PATH = "metricas_instagram.csv"

# --- FUNCIONES DE UTILIDAD ---
def timestamp(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def guardar_resultado(tipo_test, red, lat, lon, inicio, fin, estado="OK", falla="", tam=""):
    encabezado = [
        "App", "Red", "Tipo de test", "Latitud", "Longitud",
        "Fecha_Hora_Inicio", "Fecha_Hora_Fin", "Comentario", "Causa de falla", "Tamaño archivo"
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
        if "type: WIFI" in salida: return "WIFI"
        if "type: MOBILE" in salida: return "MOBILE"
    except: pass
    return "SIN_RED"

def get_location(driver):
    try:
        loc = driver.location
        return str(loc['latitude']), str(loc['longitude']) if loc else ("N/A", "N/A")
    except: return ("N/A", "N/A")

def esperar(driver, cond, timeout=30):
    return WebDriverWait(driver, timeout).until(cond)

def clic(driver, rid, desc="", timeout=8, mandatory=True):
    try:
        print(f"🔍 Intentando clic en: {desc} ({rid})")
        b = esperar(driver, EC.element_to_be_clickable((AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().resourceId("{rid}").enabled(true)')), timeout)
        b.click(); time.sleep(0.5)
        print(f"✅ Clic exitoso en: {desc}")
        return True
    except Exception as e:
        print(f"❌ Clic fallido en {desc}: {e}")
        if mandatory: raise
        return False

def ingresar_texto(driver, rid, texto, desc="", timeout=10):
    try:
        campo = esperar(driver, EC.presence_of_element_located((AppiumBy.ID, rid)), timeout)
        campo.clear(); campo.send_keys(texto); time.sleep(0.5)
        return True
    except: return False

def seleccionar_media_publicacion(driver):
    index = random.randint(4, 7)
    try:
        el = esperar(driver, EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR,
            f'new UiSelector().resourceId("com.instagram.android:id/media_picker_grid_view")'
            f'.childSelector(new UiSelector().className("android.widget.Button").instance({index}))')))
        el.click(); time.sleep(0.7)
        tam_archivo = obtener_tamano_archivo_android(ARCHIVOS_CONOCIDOS[index])
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
        print("✅ Publicación detectada como completada (desapareció el contenedor o apareció el botón Enviar).")
        guardar_resultado(tipo_metrica, red, lat, lon, inicio, timestamp(), "OK", tam=tam_archivo)
    except TimeoutException:
        print("❌ Timeout: no se detectó desaparición ni aparición del botón Enviar.")
        guardar_resultado(tipo_metrica, red, lat, lon, inicio, timestamp(), "Fail", "Timeout", tam_archivo)

def compartir(driver, tipo_metrica, red, lat, lon, inicio, tam_archivo, wait_for_id, wait_timeout=8):
    try:
        WebDriverWait(driver, wait_timeout).until(
            EC.invisibility_of_element_located((AppiumBy.ID, wait_for_id))
        )
        guardar_resultado(tipo_metrica, red, lat, lon, inicio, timestamp(), "OK", tam=tam_archivo)
    except TimeoutException:
        guardar_resultado(tipo_metrica, red, lat, lon, inicio, timestamp(), "Fail", "Timeout", tam_archivo)

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
    if not seleccionar_media(driver, index):
        guardar_resultado(tipo, red, "", "", "", "", "Fail", "No se encontró el elemento", tam_archivo)
        return
    lat, lon = get_location(driver)
    inicio = timestamp()
    tam_archivo = obtener_tamano_archivo_android(ARCHIVOS_CONOCIDOS[index])
    if click_button(driver, btn_id, "Enviar foto", False, 7):
        compartir(driver, tipo, red, lat, lon, inicio, tam_archivo, wait_for_id)
    else:
        guardar_resultado(tipo, red, lat, lon, inicio, timestamp(), "Fail", "No se encontró botón", tam_archivo)

def enviar_contenido_V(driver, tipo, index, btn_id, wait_for_id):
    if not clic(driver, "com.instagram.android:id/row_thread_composer_button_gallery", "Botón Galería"):
        return
    if not seleccionar_media(driver, index):
        guardar_resultado(tipo, red, "", "", "", "", "Fail", "No se encontró el elemento", tam_archivo)
        return
    lat, lon = get_location(driver)
    inicio = timestamp()
    tam_archivo = obtener_tamano_archivo_android(ARCHIVOS_CONOCIDOS[index])
    if click_button(driver, btn_id, "Enviar video", False, 7):
        time.sleep(2)
        compartir(driver, tipo, red, lat, lon, inicio, tam_archivo, wait_for_id, 45)
    else:
        guardar_resultado(tipo, red, lat, lon, inicio, timestamp(), "Fail", "No se encontró botón", tam_archivo)

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
            guardar_resultado(METRICAS["TEXT"], red, lat, lon, inicio, timestamp(), "Fail", "No se encontró botón", tam=tam_archivo)
    else:
        guardar_resultado(METRICAS["TEXT"], red, "", "", "", "", "Fail", "No se encontró campo de texto", tam=tam_archivo)

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
            driver.swipe(500, 1600, 500, 400, 500); time.sleep(1)
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
    ruta = f"/sdcard/Download/{nombre_archivo}"
    output = os.popen(f"adb shell ls -l {ruta}").read()
    try:
        peso_bytes = int(output.split()[4])
        peso_mb = round(peso_bytes / (1024 * 1024), 2)
        return f"{peso_mb}MB"
    except:
        return "Desconocido"

# --- DRIVER SETUP ---
def setup_driver():
    caps = {
        "platformName": "Android",
        "deviceName": "R58M795NHZF",
        "appPackage": "com.instagram.android",
        "appActivity": "com.instagram.android.activity.MainTabActivity",
        "automationName": "UiAutomator2",
        "forceAppLaunch": True,
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
    if not driver: return
    red = obtener_conectividad(driver)
    
    # --- Feed ---
    print("Cargando feed...")
    lat, lon = get_location(driver); inicio = timestamp()
    try:
        esperar(driver, EC.any_of(
            EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/recycler_view")),
            EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/refreshable_container"))
        ), 15)
        guardar_resultado(METRICAS["FEED"], red, lat, lon, inicio, timestamp())
    except:
        guardar_resultado(METRICAS["FEED"], red, lat, lon, inicio, timestamp(), "Fail", "Timeout")
    print("Cargando feed...OK")

    # --- Post ---
    print("Publicando imagen...")
    if click_tab_icon(driver, "com.instagram.android:id/tab_icon", 3, "Crear", 10) and asegurar_publicacion_activa(driver):
        exito, tam_archivo = seleccionar_media_publicacion(driver)
        if exito:
            clic(driver, "com.instagram.android:id/next_button_textview")
            clic(driver, "com.instagram.android:id/creation_next_button")
            lat, lon = get_location(driver); inicio = timestamp()
            if clic(driver, "com.instagram.android:id/share_footer_button", "Compartir"):
                compartir_P(driver, METRICAS["POST"], red, lat, lon, inicio, tam_archivo, "com.instagram.android:id/row_pending_container", "com.instagram.android:id/row_pending_media_reshare_button", 25)
    print("Publicando imagen...OK")

    # ---Reels---
    print("Reproduciendo Reel...")
    click_tab_icon(driver, "com.instagram.android:id/tab_icon", 4, "Reels", 10)
    

    if buscar_reel_con_scrubber(driver):
        lat, lon = get_location(driver); inicio = timestamp()
        if verificar_reproduccion_video(driver):
            guardar_resultado(METRICAS["RVIDEO"], red, lat, lon, inicio, timestamp(), "OK", "", "0.0MB")
        else:
            guardar_resultado(METRICAS["RVIDEO"], red, lat, lon, inicio, timestamp(), "Fail", "Reel no válido", "0.0MB")
    print("Reproduciendo Reel...OK")

    # --- Mensaje de texto ---
    print("Enviando mensaje de texto...")
    click_tab_icon(driver, "com.instagram.android:id/tab_icon", 0, "Home", 10)
    clic(driver, "com.instagram.android:id/action_bar_inbox_button")
    clic(driver, "com.instagram.android:id/row_inbox_container")
    enviar_mensaje_texto(driver, "Hola Mundo Peru", red)
    print("Enviando mensaje de texto...OK")

    index1 = random.randint(4, 7)
    index2 = random.randint(2, 3)

    print("Enviando imagen por mensaje...")
    enviar_contenido_F(driver, METRICAS["PHOTO"], 4, "com.instagram.android:id/direct_media_send_button", "com.instagram.android:id/action_icon")
    print("Enviando imagen por mensaje...OK")

    print("Enviando video por mensaje...")
    enviar_contenido_V(driver, METRICAS["VIDEO"], 2, "com.instagram.android:id/direct_media_send_button", "com.instagram.android:id/action_icon")
    print("Enviando video por mensaje...OK")

    driver.quit()
    time.sleep(1) 


# ---Funciones para el main ---
def inicializar_csv():
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "App", "Red", "Tipo de test", "Latitud", "Longitud",
                "Fecha_Hora_Inicio", "Fecha_Hora_Fin", "Estado", "Causa de falla", "Tamaño archivo"
            ])

def ejecutar_pruebas(n=1):
    for i in range(n):
        print(f"\n Iteración {i+1}")
        try:
            test_instagram()
        except Exception as e:
            print(f" Error en la iteración {i+1}: {e}")

def listar_archivos_con_tamano(carpeta="/sdcard/DriveTest"):
    salida = subprocess.getoutput(f'adb shell ls -ltlh {carpeta}')
    lista_tamanos = []
    for linea in salida.strip().split('\n'):
        columnas = linea.split()
        if len(columnas) >= 9:
            tamano = columnas[4]
            nombre_archivo = ' '.join(columnas[8:])
            if "." in nombre_archivo and not nombre_archivo.endswith("/"):
                lista_tamanos.append((nombre_archivo, tamano))

    print(f"[INFO] Tamaños de archivos en {carpeta}:")
    for i, (nombre_archivo, tamano) in enumerate(lista_tamanos):
        print(f"{i}. {nombre_archivo} - {tamano}")
    return lista_tamanos

# --- EJECUCIÓN ---
if __name__ == "__main__":
    listar_archivos_con_tamano()
    #inicializar_csv()
    #ejecutar_pruebas(3)
