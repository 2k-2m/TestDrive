from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from datetime import datetime
import time
import csv
import random
import os

# --- Constantes para Nombres de Métricas ---
METRICA_CARGA_APP_A_FEED = "Carga_Feed"
METRICA_PUBLICACION_POST = "Publicacion"
METRICA_ENVIO_MSG_TEXTO = "Ms_Texto"
METRICA_ENVIO_MSG_FOTO = "Ms_Foto"
METRICA_ENVIO_MSG_VIDEO = "Ms_Video"

# --- Helper para formatear la hora ---
def timestamp():
    """Retorna la fecha y hora actual formateada."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

# --- Función para obtener estado de conectividad ---
def obtener_estado_conectividad_real(driver):
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
    except Exception as e:
        print("Error conectividad:", e)
        return "SIN_RED"

# --- Función para configurar el driver ---
def setup_driver():
    desired_caps = {
        "platformName": "Android",
        "deviceName": "R58M795NHZF",
        "appPackage": "com.instagram.android",
        "appActivity": "com.instagram.android.activity.MainTabActivity",
        "automationName": "UiAutomator2",
        "forceAppLaunch": True,
        "noReset": True,
        "newCommandTimeout": 360
    }
    options = UiAutomator2Options().load_capabilities(desired_caps)
    try:
        print("Conectando a Appium...")
        driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
        print("Conectado.")
        return driver
    except Exception as e:
        print("Error en driver:", e)
        return None

# --- Función para guardar resultados en CSV y TXT ---
def guardar_resultado_y_tiempo_en_archivos(tipo_test, ret, latitud, longitud, fecha_hora_inicio, fecha_hora_fin, comentario="OK"):
    csv_file_path = "metricas_instagram.csv"
    txt_file_path = "tiempos_carga.txt"
    file_exists = os.path.isfile(csv_file_path)
    is_empty = os.path.getsize(csv_file_path) == 0 if file_exists else True

    with open(csv_file_path, "a", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        if not file_exists or is_empty:
            writer.writerow(["Instagram", "Tipo de test", "Ret", "Latitud", "Longitud", "Fecha_Hora_Inicio", "Fecha_Hora_Fin", "Comentario"])
        writer.writerow(["Instagram", tipo_test, ret, latitud, longitud, fecha_hora_inicio, fecha_hora_fin, comentario])
    print(f"Métrica guardada en '{csv_file_path}'.")

    with open(txt_file_path, "a", encoding="utf-8") as txt_file:
        txt_file.write(f"{fecha_hora_inicio} - {tipo_test}: Inicio: {fecha_hora_inicio}, Fin: {fecha_hora_fin}, Lat: {latitud}, Lon: {longitud}, Comentario: {comentario}\n")
    print(f"Tiempo guardado en '{txt_file_path}'.")

# --- Función para obtener la ubicación del dispositivo ---
def get_device_location(driver):
    try:
        location = driver.location
        if location and 'latitude' in location and 'longitude' in location:
            lat = str(location['latitude'])
            lon = str(location['longitude'])
            print(f"Ubicación: Lat {lat}, Lon {lon}")
            return lat, lon
    except Exception as e:
        print("Error ubicación:", e)
    print("Ubicación: N/A")
    return "N/A", "N/A"

# --- Función para medir tiempo hasta cargar el Feed ---
def measure_app_open_to_feed_time(driver):
    print("Midiendo tiempo a carga del feed...")
    try:
        WebDriverWait(driver, 45).until(
            EC.any_of(
                EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/recycler_view")),
                EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/refreshable_container"))
            )
        )
        print("Feed detectado.")
        return True
    except TimeoutException:
        print("Feed no detectado (45 seg).")
        return False
    except Exception as e:
        print("Error feed:", e)
        return False

# --- Funciones para ingresar texto ---
def enter_text_element(driver, locator, text, description="", timeout=15):
    print(f"Ingresando texto en {description}...")
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(locator)
        )
        element.clear()
        element.send_keys(text)
        print("Texto ingresado.")
        time.sleep(0.5)
        return True
    except TimeoutException:
        print(f"{description}: No encontrado en {timeout} seg.")
        return False
    except Exception as e:
        print(f"Error en {description}: {e}")
        return False

def enter_text_id(driver, resource_id, text, description="", timeout=15):
    return enter_text_element(driver, (AppiumBy.ID, resource_id), text, description, timeout)

def enter_text_ui(driver, uiautomator_string, text, description="", timeout=15):
    return enter_text_element(driver, (AppiumBy.ANDROID_UIAUTOMATOR, uiautomator_string), text, description, timeout)

# --- Funciones para hacer clic en elementos ---
def click_element(driver, locator, description="", timeout=15, mandatory=True):
    print(f"Clic en {description}...")
    try:
        element = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(locator))
        element.click()
        print("Clic exitoso.")
        time.sleep(0.5)
        return True
    except Exception as e:
        print(f"Error clic en {description}: {e}")
        if mandatory:
            raise
        return False

def click_button(driver, resource_id, description="", timeout=15, mandatory=True):
    locator = (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().resourceId("{resource_id}").enabled(true)')
    return click_element(driver, locator, description, timeout, mandatory)

def click_tab_icon(driver, resource_id, instance_index=0, description="", timeout=15, mandatory=True):
    locator = (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().resourceId("{resource_id}").instance({instance_index}).enabled(true)')
    return click_element(driver, locator, description, timeout, mandatory)

# --- Función para verificar login ---
def is_logged_in(driver):
    print("Verificando login...")
    try:
        WebDriverWait(driver, 7).until(
            EC.any_of(
                EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/title_logo")),
                EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/feed_tab_icon"))
            )
        )
        print("Autenticado.")
        return True
    except TimeoutException:
        print("No autenticado.")
        return False
    except Exception as e:
        print("Error login:", e)
        return False

# --- Función para buscar elementos de forma segura ---
def find_elements_safely(driver, by, value, timeout=10, description="Elementos"):
    try:
        print(f"Buscando {description} ({by}: {value})...")
        WebDriverWait(driver, timeout).until(EC.presence_of_all_elements_located((by, value)))
        elements = driver.find_elements(by, value)
        print(f"Encontrados {len(elements)} {description}.")
        return elements
    except TimeoutException:
        print(f"No se encontraron {description} en {timeout} seg.")
        return []
    except Exception as e:
        print(f"Error al buscar {description}: {e}")
        return []

# --- Función para seleccionar una foto aleatoria ---
def random_photo(driver, thumbnail_locators):
    print("Seleccionando miniatura aleatoria...")
    photo_elements = []
    for by, value in thumbnail_locators:
        photo_elements = find_elements_safely(driver, by, value, timeout=10, description="miniaturas de foto")
        if photo_elements:
            break
    if photo_elements:
        selected = random.choice(photo_elements)
        desc = selected.get_attribute("content-desc") or selected.text or f"Elemento ({selected.tag_name})"
        print(f"Miniatura seleccionada: {desc}")
        selected.click()
        print("Clic ejecutado.")
        time.sleep(2)
    else:
        raise Exception("No se encontraron miniaturas de foto con los selectores proporcionados.")

# --- Función para asegurar que la opción "PUBLICACIÓN" esté activa ---
def asegurar_publicacion_activa(driver, timeout=5):
    print("Verificando opción 'PUBLICACIÓN'...")
    try:
        elem = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((
                AppiumBy.XPATH,
                '//android.widget.TextView[@content-desc="PUBLICACIÓN"]'
            ))
        )
        if elem.is_selected() or "selected" in (elem.get_attribute("selected") or ""):
            print("'PUBLICACIÓN' ya está activa.")
            return True
        else:
            print("Activando 'PUBLICACIÓN'...")
            return click_button(driver, "com.instagram.android:id/cam_dest_feed", "PUBLICACIÓN")
    except Exception as e:
        print(f"Error en 'PUBLICACIÓN': {e}")
        return False

# --- Función para seleccionar una miniatura desde la galería ---
def select_from_gallery(driver, instance_index, gallery_id="com.instagram.android:id/gallery_grid", thumbnail_class_name="android.widget.CheckBox", timeout=15):
    print("Seleccionando miniatura de foto/video de la galería...")
    selector = (f'new UiSelector().resourceId("{gallery_id}")'
                f'.childSelector(new UiSelector().className("{thumbnail_class_name}").instance({instance_index}))')
    try:
        thumbnail = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, selector))
        )
        desc = thumbnail.get_attribute("content-desc") or thumbnail.text or f"miniatura índice {instance_index}"
        print(f"Miniatura encontrada: {desc}")
        thumbnail.click()
        print("Clic ejecutado.")
        time.sleep(2)
        return True
    except TimeoutException:
        print(f"Miniatura no encontrada en {timeout} seg.")
        return False
    except NoSuchElementException:
        print("Miniatura no encontrada de inmediato.")
        return False
    except Exception as e:
        print(f"Error al hacer clic en la miniatura: {e}")
        return False

# --- Definición de locators para miniaturas de fotos ---
PHOTO_THUMBNAIL_LOCATORS = [
    (AppiumBy.XPATH, '//android.widget.GridView[@resource-id="com.instagram.android:id/media_picker_grid_view"]//android.widget.Button'),
    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().resourceId("com.instagram.android:id/media_picker_grid_view").childSelector(new UiSelector().className("android.widget.Button"))'),
    (AppiumBy.CLASS_NAME, "android.widget.Button"),
]

# --- Función genérica para enviar mensaje con media (foto o video) ---
def enviar_mensaje_con_media(driver, Red, METRICA, selector_index, enviar_descripcion, timeout_confirmation=60, pre_confirmation_sleep=0):
    time.sleep(2)
    if click_button(driver, "com.instagram.android:id/row_thread_composer_button_gallery", "Botón Galería"):
        if select_from_gallery(driver, selector_index):
            lat, lon = get_device_location(driver)
            inicio = timestamp()
            print(f"\n⏱️ Medición: Tiempo de envío de mensaje con {enviar_descripcion}...")
            if click_button(driver, "com.instagram.android:id/media_thumbnail_tray_button", f"Enviar {enviar_descripcion}", mandatory=False, timeout=7):
                try:
                    if pre_confirmation_sleep > 0:
                        time.sleep(pre_confirmation_sleep)
                    print(f"Esperando confirmación de envío de {enviar_descripcion}...")
                    WebDriverWait(driver, timeout_confirmation).until(
                        EC.invisibility_of_element_located((AppiumBy.ID, "com.instagram.android:id/action_icon"))
                    )
                    fin = timestamp()
                    print(f"✅ Mensaje con {enviar_descripcion} enviado y confirmado.")
                    guardar_resultado_y_tiempo_en_archivos(
                        METRICA, Red, lat, lon, inicio, fin, "OK"
                    )
                except TimeoutException:
                    fin = timestamp()
                    print(f"⚠️ Timeout al confirmar envío de {enviar_descripcion} en {timeout_confirmation} seg.")
                    guardar_resultado_y_tiempo_en_archivos(
                        METRICA, Red, lat, lon, inicio, fin, "Timeout de confirmación"
                    )
            else:
                fin = timestamp()
                print(f"❌ No se pudo hacer clic en Enviar {enviar_descripcion}.")
                guardar_resultado_y_tiempo_en_archivos(
                    METRICA, Red, lat, lon, inicio, fin, f"No se hizo clic en Enviar {enviar_descripcion}"
                )
        else:
            lat, lon = "N/A", "N/A"
            inicio = timestamp()
            fin = inicio
            print(f"❌ No se pudo seleccionar {enviar_descripcion} de la galería del chat.")
            guardar_resultado_y_tiempo_en_archivos(
                METRICA, Red, lat, lon, inicio, fin, f"No se pudo seleccionar {enviar_descripcion}"
            )
    else:
        lat, lon = "N/A", "N/A"
        inicio = timestamp()
        fin = inicio
        print("❌ No se pudo hacer clic en Botón Galería en el chat.")
        guardar_resultado_y_tiempo_en_archivos(
            METRICA, Red, lat, lon, inicio, fin, "No se hizo clic en Botón Galería"
        )

# --- Función principal de test ---
def test_instagram_automation():
    driver = setup_driver()
    if not driver:
        print("Error: No se pudo iniciar el driver.")
        return

    try:
        Red = obtener_estado_conectividad_real(driver)
        print("\n--- Instagram Automation Started ---")

        # 1. Medición: Carga de App -> Feed
        lat_inicio_app_feed, lon_inicio_app_feed = get_device_location(driver)
        inicio_feed = timestamp()
        if measure_app_open_to_feed_time(driver):
            fin_feed = timestamp()
            guardar_resultado_y_tiempo_en_archivos(
                METRICA_CARGA_APP_A_FEED, Red, lat_inicio_app_feed, lon_inicio_app_feed,
                inicio_feed, fin_feed, "OK"
            )
        else:
            fin_feed = timestamp()
            guardar_resultado_y_tiempo_en_archivos(
                METRICA_CARGA_APP_A_FEED, Red, lat_inicio_app_feed, lon_inicio_app_feed,
                inicio_feed, fin_feed, "Feed no detectado"
            )
            print("⚠️ Feed no detectado. Abortando test.")
            return

        # 2. Proceso de Login (si es necesario)
        if not is_logged_in(driver):
            print("Login: Usuario no autenticado. Se prosigue con flujo de login.")
            # Aquí se puede agregar la lógica de login si es necesario.
        else:
            print("Login: Usuario ya autenticado.")
            time.sleep(2)

        # 3. Flujo de Publicación de Post
        click_tab_icon(driver, "com.instagram.android:id/tab_avatar", instance_index=0, description="Avatar Tab")
        click_tab_icon(driver, "com.instagram.android:id/tab_icon", instance_index=2, description="Nuevo Post", timeout=10)
        print("✅ 'Crear (+)' presionado.")
        if not asegurar_publicacion_activa(driver):
            print("❌ No se pudo activar la opción 'PUBLICACIÓN'. Abortando publicación.")
            return

        random_photo(driver, PHOTO_THUMBNAIL_LOCATORS)
        click_button(driver, "com.instagram.android:id/next_button_textview", "Siguiente (Selección de Media)")
        click_button(driver, "com.instagram.android:id/creation_next_button", "Siguiente creación")
        lat_inicio_post, lon_inicio_post = get_device_location(driver)
        inicio_post = timestamp()
        print("\n⏱️ Iniciando medición: Publicación del post...")
        if click_button(driver, "com.instagram.android:id/share_footer_button", "Compartir publicación"):
            try:
                WebDriverWait(driver, 90).until(
                    EC.any_of(
                        EC.invisibility_of_element_located((AppiumBy.XPATH, "//*[contains(@text, 'Finalizando') or contains(@text, 'Finishing')]")),
                        EC.invisibility_of_element_located((AppiumBy.XPATH, "//*[contains(@text, 'Compartiendo') or contains(@text, 'Sharing')]")),
                        EC.element_to_be_clickable((AppiumBy.ID, "com.instagram.android:id/feed_tab_icon"))
                    )
                )
                fin_post = timestamp()
                print("✅ Publicación completada y confirmada.")
                guardar_resultado_y_tiempo_en_archivos(
                    METRICA_PUBLICACION_POST, Red, lat_inicio_post, lon_inicio_post,
                    inicio_post, fin_post, "OK"
                )
            except TimeoutException:
                fin_post = timestamp()
                print("⚠️ Timeout al confirmar publicación en 90 seg.")
                guardar_resultado_y_tiempo_en_archivos(
                    METRICA_PUBLICACION_POST, Red, lat_inicio_post, lon_inicio_post,
                    inicio_post, fin_post, "Timeout de confirmación"
                )
        else:
            fin_post = timestamp()
            guardar_resultado_y_tiempo_en_archivos(
                METRICA_PUBLICACION_POST, Red, lat_inicio_post, lon_inicio_post,
                inicio_post, fin_post, "No se hizo clic en Compartir"
            )
            print("❌ No se hizo clic en 'Compartir'. Test abortado.")
            return

        # 4. Flujo de Mensaje de Texto
        time.sleep(2)
        click_button(driver, "com.instagram.android:id/action_bar_inbox_button", "Inbox (Mensajes)")
        click_button(driver, "com.instagram.android:id/row_inbox_container", "Entrar al Primer Chat")
        lat_inicio_msg_texto, lon_inicio_msg_texto = get_device_location(driver)
        inicio_msg_texto = timestamp()
        print("\n⏱️ Medición: Tiempo de envío de mensaje de texto...")
        if enter_text_ui(driver, 'new UiSelector().resourceId("com.instagram.android:id/row_thread_composer_edittext")', "Hola prueba", "Escribir un hola"):
            if click_button(driver, "com.instagram.android:id/row_thread_composer_send_button_container", "Enviar mensaje", mandatory=False, timeout=7):
                try:
                    print("Esperando confirmación de envío de texto...")
                    WebDriverWait(driver, 30).until(
                        EC.invisibility_of_element_located((AppiumBy.ID, "com.instagram.android:id/action_icon"))
                    )
                    fin_msg_texto = timestamp()
                    print("✅ Mensaje de texto enviado y confirmado.")
                    guardar_resultado_y_tiempo_en_archivos(
                        METRICA_ENVIO_MSG_TEXTO, Red, lat_inicio_msg_texto, lon_inicio_msg_texto,
                        inicio_msg_texto, fin_msg_texto, "OK"
                    )
                except TimeoutException:
                    fin_msg_texto = timestamp()
                    print("⚠️ Timeout al confirmar envío de mensaje de texto.")
                    guardar_resultado_y_tiempo_en_archivos(
                        METRICA_ENVIO_MSG_TEXTO, Red, lat_inicio_msg_texto, lon_inicio_msg_texto,
                        inicio_msg_texto, fin_msg_texto, "Timeout de confirmación"
                    )
            else:
                fin_msg_texto = timestamp()
                guardar_resultado_y_tiempo_en_archivos(
                    METRICA_ENVIO_MSG_TEXTO, Red, lat_inicio_msg_texto, lon_inicio_msg_texto,
                    inicio_msg_texto, fin_msg_texto, "No se hizo clic en Enviar"
                )
                print("❌ No se hizo clic en Enviar Mensaje.")
        else:
            fin_msg_texto = timestamp()
            guardar_resultado_y_tiempo_en_archivos(
                METRICA_ENVIO_MSG_TEXTO, Red, lat_inicio_msg_texto, lon_inicio_msg_texto,
                inicio_msg_texto, fin_msg_texto, "No se pudo ingresar texto"
            )
            print("❌ No se pudo ingresar texto en el chat.")

        # 5. Flujo de Mensaje con Foto
        enviar_mensaje_con_media(driver, Red, METRICA_ENVIO_MSG_FOTO, selector_index=2, enviar_descripcion="foto")
        
        # 6. Flujo de Mensaje con Video
        enviar_mensaje_con_media(driver, Red, METRICA_ENVIO_MSG_VIDEO, selector_index=0, enviar_descripcion="Video", pre_confirmation_sleep=3)
        
        print("\n✅ Flujo principal de acciones completado.")
        time.sleep(2)
    except Exception as e:
        print(f"❌ Ocurrió un error durante la prueba: {e}")
        ts_err = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot = f"error_general_test_{ts_err}.png"
        try:
            driver.save_screenshot(screenshot)
            print(f"Screenshot guardado como '{screenshot}'.")
        except Exception as e_s:
            print(f"Error al guardar screenshot: {e_s}")
    finally:
        print("\n--- Automation Finished ---")
        driver.quit()
        print("Driver finalizado.")

# --- Bloque principal ---
if __name__ == "__main__":
    csv_file_path = "metricas_instagram.csv"
    # Crear/inicializar el archivo CSV si no existe o está vacío.
    if not os.path.isfile(csv_file_path) or os.path.getsize(csv_file_path) == 0:
        with open(csv_file_path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(["Instagram", "Tipo de test", "Ret", "Latitud", "Longitud", "Fecha_Hora_Inicio", "Fecha_Hora_Fin", "Comentario"])
        print(f"📄 Archivo '{csv_file_path}' creado/inicializado.")

    repeticiones = 2
    for i in range(repeticiones):
        print(f"\n🔁 Ejecutando iteración {i + 1} de {repeticiones}...")
        try:
            test_instagram_automation()
        except Exception as e:
            print(f"❌ Error en la iteración {i + 1}: {e}")
