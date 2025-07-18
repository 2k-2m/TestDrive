# --- IMPORTS & CONFIGURACIÓN INICIAL ---
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import time, csv, random, os

# --- CONSTANTES ---
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
            'args': [],
            'includeStderr': True,
            'timeout': 5000
        })['stdout']

        redes_conectadas = []
        for bloque in salida.split("NetworkAgentInfo")[1:]:
            if "state: CONNECTED" in bloque and "VALIDATED" in bloque:
                if "type: WIFI" in bloque:
                    redes_conectadas.append("WIFI")
                elif "type: MOBILE" in bloque:
                    redes_conectadas.append("MOBILE")

        if "WIFI" in redes_conectadas:
            return "WIFI"
        elif "MOBILE" in redes_conectadas:
            return "MOBILE"
        else:
            return "SIN_RED"
    except: return "SIN_RED"

def get_location(driver):
    try:
        loc = driver.location
        return str(loc['latitude']), str(loc['longitude']) if loc else ("N/A", "N/A")
    except: return ("N/A", "N/A")

def esperar(driver, cond, timeout=30):
    return WebDriverWait(driver, timeout).until(cond)

def clic(driver, rid, desc="", timeout=8, mandatory=True):
    try:
        b = esperar(driver, EC.element_to_be_clickable((AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().resourceId("{rid}").enabled(true)')), timeout)
        b.click(); time.sleep(0.5)
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

def seleccionar_media(driver, index):
    try:
        sel = esperar(driver, EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().resourceId("com.instagram.android:id/gallery_grid").childSelector(new UiSelector().className("android.widget.CheckBox").instance({index}))')))
        sel.click(); time.sleep(.7)
        return True
    except: return False

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
    except Exception as e:
        if mandatory:
            raise
        return False

def enviar_contenido_F(driver, tipo, index, btn_id, tam_archivo, wait_for_id):
    if not clic(driver, "com.instagram.android:id/row_thread_composer_button_gallery", "Botón Galería"):
        return

    if not seleccionar_media(driver, index):
        guardar_resultado(tipo, red, "", "", "", "", "Fail", "No se encontro el elemento", tam_archivo)
        return

    lat, lon = get_location(driver)
    inicio = timestamp()
    
    if click_button(driver, btn_id, "Enviar foto", False, 7):
        compartir(driver, tipo, red, lat, lon, inicio, tam_archivo, wait_for_id)
    else:
        guardar_resultado(tipo, red, lat, lon, inicio, timestamp(), "Fail", "No se encontro boton", tam_archivo)

def enviar_contenido_V(driver, tipo, index, btn_id, tam_archivo, wait_for_id):
    clic(driver, "com.instagram.android:id/row_thread_composer_button_gallery", "Botón Galería")
    if not seleccionar_media(driver, index):
        guardar_resultado(tipo, red, "", "", "", "", "Fail", "No se encontro el elemento", tam_archivo)
        return

    lat, lon = get_location(driver)
    inicio = timestamp()
    
    if click_button(driver, btn_id, "Enviar foto", False, 7):
        time.sleep(2)
        compartir(driver, tipo, red, lat, lon, inicio, tam_archivo, wait_for_id, 45)
    else:
        guardar_resultado(tipo, red, lat, lon, inicio, timestamp(), "Fail", "No se encontro boton", tam_archivo)

def find_elements_safely(driver, by, value, timeout=10, description="Elementos"):
    try:
        WebDriverWait(driver, timeout).until(EC.presence_of_all_elements_located((by, value)))
        elements = driver.find_elements(by, value)
        print(f" Se encontraron {len(elements)}.")
        return elements
    except TimeoutException:
        print(f"No se encontraron elementos en {timeout} segundos.")
        return []
    except Exception as e:
        print(f"Error al buscar elementos para : {e}")
        return []

def random_photo(driver, thumbnail_locators):
    photo_elements = []
    for by, value in thumbnail_locators:
        all_elements = find_elements_safely(driver, by, value, timeout=10, description="Miniaturas")
        if all_elements:
            # Filtrar solo los elementos que en content-desc indiquen que son FOTOS
            filtered_elements = [
                el for el in all_elements
                if "miniatura de foto" in (el.get_attribute("content-desc") or "").lower()]
            
            if filtered_elements:
                photo_elements = filtered_elements
                break

    if photo_elements:
        selected = random.choice(photo_elements)
        selected.click()
        time.sleep(.5)
    else:
        raise Exception("No se encontraron miniaturas de fotos.")

def click_tab_icon(driver, resource_id, instance_index=0, description="", timeout=15, mandatory=True):
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((
                AppiumBy.ANDROID_UIAUTOMATOR,
                f'new UiSelector().resourceId("{resource_id}").instance({instance_index}).enabled(true)'
            ))
        )
        element.click()
        time.sleep(0.5)
        return True
    except Exception as e:
        if mandatory:
            raise
        return False

def enviar_mensaje_texto(driver, mensaje, red):
    tam_archivo = f"{len(mensaje)} C"
    if ingresar_texto(driver, "com.instagram.android:id/row_thread_composer_edittext", mensaje):
        lat, lon = get_location(driver)
        inicio = timestamp()
        if clic(driver, "com.instagram.android:id/row_thread_composer_send_button_container", "Enviar texto", timeout=7, mandatory=False):
            compartir(driver, tipo_metrica=METRICAS["TEXT"], red=red, lat=lat, lon=lon, inicio=inicio, tam_archivo=tam_archivo, wait_for_id="com.instagram.android:id/action_icon")
        else:
            guardar_resultado(METRICAS["TEXT"], red, lat, lon, inicio, timestamp(), "Fail", "No se encontró botón", tam=tam_archivo)
    else:
        guardar_resultado(METRICAS["TEXT"], red, "", "", "", "", "Fail", "No se encontró campo de texto", tam=tam_archivo)

def enviar_mensaje_texto(driver, mensaje, red):
    if ingresar_texto(driver, "com.instagram.android:id/row_thread_composer_edittext", mensaje):
        lat, lon = get_location(driver)
        inicio = timestamp()
        if clic(driver, "com.instagram.android:id/row_thread_composer_send_button_container", "Enviar texto", timeout=7, mandatory=False):
            compartir(driver, tipo_metrica=METRICAS["TEXT"], red=red, lat=lat, lon=lon, inicio=inicio, tam_archivo="1KB", wait_for_id="com.instagram.android:id/action_icon")
        else:
            guardar_resultado(METRICAS["TEXT"], red, lat, lon, inicio, timestamp(), "Fail", "No se encontro boton", "-1")
    else:
        guardar_resultado(METRICAS["TEXT"], red, "", "", "", "", "Fail", "No se encontro campo de texto", "-1")

def asegurar_publicacion_activa(driver, timeout=5):
    try:
        publicacion_btn = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/cam_dest_feed")))
        publicacion_btn.click()
        return True

    except Exception:
        print("Intentando primero con 'REEL'...")

    try:
        reel_btn = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "REEL")))
        reel_btn.click()
        print("'REEL' clickeado.")

        publicacion_btn = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/cam_dest_feed")))
        publicacion_btn.click()
        print("'PUBLICACIÓN' fue activada")
        return True

    except Exception as e:
        print(f" No se pudo activar 'PUBLICACIÓN' incluso después de seleccionar 'REEL': {e}")
        return False

def buscar_reel_con_scrubber(driver, intentos_maximos=5):
    id_scrubber = "com.instagram.android:id/scrubber"

    for intento in range(intentos_maximos):
        print(f"Buscando reel con scrubber... intento {intento + 1}")
        try:
            driver.find_element(AppiumBy.ID, id_scrubber)
            print("Scrubber encontrado.")
            return True
        except:
            print("Haciendo scroll...")
            driver.swipe(start_x=500, start_y=1600, end_x=500, end_y=400, duration=500)
            time.sleep(2)

    print("ningún reel con scrubber.")
    return False

def verificar_reproduccion_video(driver, duracion_segundos=15, check_interval=2):
    id_scrubber = "com.instagram.android:id/scrubber"
    tiempo_total = 0
    progreso_anterior = -1
    intentos_sin_scrubber = 0

    while tiempo_total < duracion_segundos:
        try:
            scrubber = driver.find_element(AppiumBy.ID, id_scrubber)
            progreso_actual = float(scrubber.get_attribute("text"))

            if progreso_actual == progreso_anterior:
                print("Video detenido por lag.")
                return False

            progreso_anterior = progreso_actual
            intentos_sin_scrubber = 0  # reset
        except:
            print("Scrubber no encontrado.")
            intentos_sin_scrubber += 1
            if intentos_sin_scrubber >= 3:
                print("Video no se está reproduciendo.")
                return False

        time.sleep(check_interval)
        tiempo_total += check_interval

    print("Video reproducido correctamente por 15 segundos.")
    return True

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
        return webdriver.Remote("http://127.0.0.1:4723", options= UiAutomator2Options().load_capabilities(caps))
    except Exception as e:
        print(f"No se pudo iniciar Appium: {e}")
        return None

# --- PRUEBA PRINCIPAL ---
def test_instagram():
    global red
    driver = setup_driver()
    if not driver: return

    red = obtener_conectividad(driver)

    # 1. Cargar feed
    lat, lon = get_location(driver); inicio = timestamp()
    try:
        esperar(driver, EC.any_of(
            EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/recycler_view")),
            EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/refreshable_container"))), 15)
        guardar_resultado(METRICAS["FEED"], red, lat, lon, inicio, timestamp())
        print("\n Se cargo el Feed")
    except:
        guardar_resultado(METRICAS["FEED"], red, lat, lon, inicio, timestamp(), "Fail", "Timeout")
        print("\n No se cargo el Feed")

    # 2. Publicar post
    if not click_tab_icon(driver, "com.instagram.android:id/tab_icon", 3, "Icono crear (+)", timeout=10):return
    if not asegurar_publicacion_activa(driver):return
    random_photo(driver, PHOTO_THUMBNAIL_LOCATORS)
    clic(driver, "com.instagram.android:id/next_button_textview", "Next")
    clic(driver, "com.instagram.android:id/creation_next_button", "Next creación")
    lat, lon = get_location(driver); inicio = timestamp()
    if clic(driver, "com.instagram.android:id/share_footer_button", "Compartir"):
        compartir(driver, tipo_metrica=METRICAS["POST"], red=red, lat=lat, lon=lon, inicio=inicio, tam_archivo="2MB",wait_for_id="com.instagram.android:id/row_pending_container", wait_timeout=25)
        print("\n Se cargo el Post")

    # 3. Ver video
    click_tab_icon(driver, "com.instagram.android:id/tab_icon", 4, "Reels", timeout=10)
    print("\n Reproduciendo Video")
    lat, lon = get_location(driver)
    inicio = timestamp()
    if buscar_reel_con_scrubber(driver):
        if verificar_reproduccion_video(driver):
            guardar_resultado(METRICAS["RVIDEO"], red, lat, lon, inicio, timestamp(), "OK", "", "0.0MB")
            print("\n Se reprodujo el Video")
        else:
            guardar_resultado(METRICAS["RVIDEO"], red, lat, lon, inicio, timestamp(), "Fail", "Video detenido", "0.0MB")
    else:
        guardar_resultado(METRICAS["RVIDEO"], red, lat, lon, inicio, timestamp(), "Fail", "No se encontró scrubber", "0.0MB")

    # 4. Enviar texto
    click_tab_icon(driver, "com.instagram.android:id/tab_icon", 0, "Home", timeout=10)
    clic(driver, "com.instagram.android:id/action_bar_inbox_button", "Inbox")
    clic(driver, "com.instagram.android:id/row_inbox_container", "Primer Chat")
    enviar_mensaje_texto(driver, "Hola Mundo", red)
    print("\n Se envio mensaje")

    # 5. Enviar foto
    enviar_contenido_F(driver, tipo=METRICAS["PHOTO"], index=2, btn_id="com.instagram.android:id/direct_media_send_button", tam_archivo="2MB", wait_for_id="com.instagram.android:id/action_icon")
    print("\n Se envio foto")

    # 6. Enviar video
    enviar_contenido_V(driver, tipo=METRICAS["VIDEO"], index=0, btn_id="com.instagram.android:id/direct_media_send_button", tam_archivo="20MB", wait_for_id="com.instagram.android:id/action_icon")
    print("\n Se envio video")

    driver.quit()

# --- EJECUCIÓN ---
if __name__ == "__main__":
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Instagram", "Tipo de test", "Ret", "Latitud", "Longitud",
                "Fecha_Hora_Inicio", "Fecha_Hora_Fin", "Comentario", "Causa de falla", "Tamaño archivo"
            ])
    for i in range(1):
        print(f"\n Iteración {i+1}")
        try:
            test_instagram()
        except Exception as e:
            print(f" Error en la iteración {i+1}: {e}")
