from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support import expected_conditions as EC
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


#Función de código para detectar red:
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
        print(f"⚠️ Error al verificar conectividad real: {e}")
        return "SIN_RED"


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
        print("Attempting to connect to Appium server...")
        driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
        print("✅ Successfully connected to Appium server.")
        return driver
    except Exception as e:
        print(f"❌ Failed to connect to Appium server or start session: {e}")
        return None

# --- Función ACTUALIZADA para Guardar Resultados en CSV y TXT ---
def guardar_resultado_y_tiempo_en_archivos(tipo_test, ret, latitud, longitud, fecha_hora_inicio, fecha_hora_fin, comentario="OK"):
    csv_file_path = "metricas_instagram.csv"
    txt_file_path = "tiempos_carga.txt" # Path para el archivo TXT

    # --- Escribir en CSV ---
    file_exists = os.path.isfile(csv_file_path)
    is_empty = os.path.getsize(csv_file_path) == 0 if file_exists else True

    with open(csv_file_path, "a", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file, delimiter=';')
        if not file_exists or is_empty:
            writer.writerow([
                "Instagram", "Ret", "Tipo de test", "Latitud", "Longitud",
                "Fecha_Hora_Inicio", "Fecha_Hora_Fin", "Comentario"
            ])
        writer.writerow([
            "Instagram", ret, tipo_test, latitud, longitud,
            fecha_hora_inicio, fecha_hora_fin, comentario
        ])
    print(f"📝 Métrica guardada en '{csv_file_path}'.")

    # --- Escribir en TXT ---
    # Calcular la duración para el archivo TXT
    # Convertir a datetime objects para calcular la diferencia
    fmt = "%Y-%m-%d %H:%M:%S.%f"
    start_dt = datetime.strptime(fecha_hora_inicio, fmt)
    end_dt = datetime.strptime(fecha_hora_fin, fmt)

    with open(txt_file_path, "a", encoding="utf-8") as txt_file:
        txt_file.write(
            f"{fecha_hora_inicio} - {tipo_test}: "
            f"Inicio: {fecha_hora_inicio}, Fin: {fecha_hora_fin}, "
            f"Lat: {latitud}, Lon: {longitud}, Comentario: {comentario}\n"
        )
    print(f"📝 Tiempo guardado en '{txt_file_path}'.")


# --- Resto de las funciones (get_device_location, measure_app_open_to_feed_time,
# enter_text_id, enter_text_ui, click_button, click_tab_icon, is_logged_in,
# find_elements_safely, random_photo, asegurar_publicacion_activa, select_from_gallery)
# sin cambios. No las incluyo aquí para evitar la repetición del código que ya funciona.
# Asegúrate de copiarlas desde tu script original o desde mi última respuesta. ---

# Incluyo las funciones de interacción aquí para que el código sea completo y runnable.
# Si ya las tienes en tu archivo, no necesitas pegarlas de nuevo.

def get_device_location(driver):
    latitude, longitude = "N/A", "N/A"
    try:
        location = driver.location
        if location and 'latitude' in location and 'longitude' in location:
            latitude = str(location['latitude'])
            longitude = str(location['longitude'])
            print(f"🌍 Ubicación del dispositivo: Lat {latitude}, Lon {longitude}")
        else:
            print("⚠️ No se pudo obtener la ubicación (driver.location retornó None o incompleto).")
    except Exception as e:
        print(f"❌ Error al obtener la ubicación del dispositivo: {e}")
        print("Asegúrate de que los servicios de ubicación estén activados y Appium tenga permisos.")
    return latitude, longitude

def measure_app_open_to_feed_time(driver):
    print("\n⏱️ Medición: Tiempo desde apertura de app hasta carga del For You Page...")
    try:
        WebDriverWait(driver, 45).until(
            EC.any_of(
                EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/recycler_view")),
                EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/refreshable_container")),
            )
        )
        print("✅ Feed (For You page) detectado por uno de los indicadores comunes.")
        return True
    except TimeoutException:
        print("❌ No se pudo detectar el contenedor del feed/FYP (indicadores comunes) en 45 segundos.")
        return False
    except Exception as e:
        print(f"❌ Error al esperar el feed: {e}")
        return False

def enter_text_id(driver, resource_id, text_to_enter, description="",timeout=15):
    print(f"Buscando '{description}' para ingresar texto...")
    try:
        text_field = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((AppiumBy.ID, resource_id))
        )
        text_field.clear()
        text_field.send_keys(text_to_enter)
        print(f"✅ Texto ingresado exitosamente en '{description}'")
        time.sleep(0.5)
        return True
    except TimeoutException:
        print(f"❌ El '{description}'no se encontró en {timeout} segundos.")
        return False
    except Exception as e:
        print(f"❌ Error al ingresar texto en '{description}'): {e}")
        return False

def enter_text_ui(driver, uiautomator_string, text_to_enter, description="", timeout=15):
    print(f"Buscando '{description}' para ingresar texto...")
    try:
        text_field = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, uiautomator_string))
        )
        text_field.clear()
        text_field.send_keys(text_to_enter)
        print(f"✅ Texto ingresado exitosamente en '{description}': '{text_to_enter}'")
        time.sleep(0.5)
        return True
    except TimeoutException:
        print(f"❌ El '{description}' no se encontró en {timeout} segundos.")
        return False
    except Exception as e:
        print(f"❌ Error al ingresar texto en '{description}' {e}")
        return False

def click_button(driver, resource_id, description="", timeout=15, mandatory=True):
    print(f"🔍 Esperando {description} (ID: {resource_id})")
    try:
        button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((
                AppiumBy.ANDROID_UIAUTOMATOR,
                f'new UiSelector().resourceId("{resource_id}").enabled(true)'
            ))
        )
        button.click()
        print(f"✅ Click exitoso en: {description}")
        time.sleep(.5)
        return True
    except Exception as e:
        print(f"❌ Falló el clic en {description}: {e}")
        if mandatory:
            raise
        return False

def click_tab_icon(driver, resource_id, instance_index=0, description="", timeout=15, mandatory=True):
    print(f"🔍 Esperando {description} (ID: {resource_id}, Instancia: {instance_index})")
    try:
        icon = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((
                AppiumBy.ANDROID_UIAUTOMATOR,
                f'new UiSelector().resourceId("{resource_id}").instance({instance_index}).enabled(true)'
            ))
        )
        icon.click()
        print(f"✅ Click exitoso en: {description}")
        time.sleep(.5)
        return True
    except Exception as e:
        print(f"❌ Falló el clic en {description}: {e}")
        if mandatory:
            raise
        return False

def is_logged_in(driver):
    print("Checking if already logged in by looking for Instagram logo or feed...")
    try:
        WebDriverWait(driver, 7).until( # Ligeramente más tiempo
            EC.any_of(
                EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/title_logo")),
                EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/feed_tab_icon")),
            )
        )
        print("✅ User appears to be logged in.")
        return True
    except TimeoutException:
        print("❌ User is likely not logged in (logo/feed not found quickly).")
        return False
    except Exception as e:
        print(f"An error occurred while checking login status: {e}")
        return False

PHOTO_THUMBNAIL_LOCATORS = [
    (AppiumBy.XPATH, '//android.widget.GridView[@resource-id="com.instagram.android:id/media_picker_grid_view"]//android.widget.Button'),
    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().resourceId("com.instagram.android:id/media_picker_grid_view").childSelector(new UiSelector().className("android.widget.Button"))'),
    (AppiumBy.CLASS_NAME, "android.widget.Button"),
]

def find_elements_safely(driver, by, value, timeout=10, description="Elementos"):
    try:
        print(f"Buscando '{description}' con el localizador {by} y valor '{value}'...")
        
        WebDriverWait(driver, timeout).until(EC.presence_of_all_elements_located((by, value)))
        elements = driver.find_elements(by, value)
        print(f"✅ Se encontraron {len(elements)} elementos para '{description}'.")
        return elements
    except TimeoutException:
        print(f"❌ No se encontraron elementos para '{description}' en {timeout} segundos.")
        return []
    except Exception as e:
        print(f"❌ Error al buscar elementos para '{description}': {e}")
        return []

def random_photo(driver, thumbnail_locators):
    print("\n--- Intentando seleccionar una miniatura de foto aleatoriamente ---")
    photo_elements = []
    
    for by, value in thumbnail_locators:
        all_elements = find_elements_safely(driver, by, value, timeout=10, description="Miniaturas")
        if all_elements:
            # Filtrar solo los elementos que en content-desc indiquen que son FOTOS
            filtered_elements = [
                el for el in all_elements
                if "miniatura de foto" in (el.get_attribute("content-desc") or "").lower()
            ]
            if filtered_elements:
                photo_elements = filtered_elements
                break

    if photo_elements:
        selected = random.choice(photo_elements)
        desc = selected.get_attribute("content-desc") or selected.text or "Elemento sin descripción"
        print(f"✅ Seleccionando miniatura aleatoria de foto: '{desc}'")
        selected.click()
        print("✅ Clic en miniatura exitoso.")
        time.sleep(2)
    else:
        raise Exception("❌ No se encontraron miniaturas de fotos (videos excluidos).")
    

def asegurar_publicacion_activa(driver, timeout=5):
    try:
        publicacion_btn = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/cam_dest_feed"))
        )
        publicacion_btn.click()
        print("✅ 'PUBLICACIÓN' fue activada directamente.")
        return True

    except Exception:
        print("⚠️ No se pudo hacer clic en 'PUBLICACIÓN'. Intentando primero con 'REEL'...")

    try:
        reel_btn = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "REEL"))
        )
        reel_btn.click()
        print("🎯 'REEL' fue seleccionado correctamente.")

        publicacion_btn = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/cam_dest_feed"))
        )
        publicacion_btn.click()
        print("✅ 'PUBLICACIÓN' fue activada después de seleccionar 'REEL'.")
        return True

    except Exception as e:
        print(f"❌ No se pudo activar 'PUBLICACIÓN' incluso después de seleccionar 'REEL': {e}")
        return False


def select_from_gallery(driver, instance_index, gallery_id="com.instagram.android:id/gallery_grid", thumbnail_class_name="android.widget.CheckBox", timeout=15):
    print(f"\n--- Intentando seleccionar la miniatura de foto/video de la galería")
    
    uiautomator_selector = (
        f'new UiSelector().resourceId("{gallery_id}")'
        f'.childSelector(new UiSelector().className("{thumbnail_class_name}").instance({instance_index}))'
    )

    try:
        photo_thumbnail = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, uiautomator_selector))
        )
        
        photo_description = photo_thumbnail.get_attribute('content-desc') or photo_thumbnail.text or f"miniatura en índice {instance_index} de la galería"
        print(f"✅ Seleccionando miniatura de foto/video: '{photo_description}'")
        photo_thumbnail.click()
        print(f"✅ Clic en miniatura de foto/video en índice {instance_index} exitoso.")
        time.sleep(2) # Esperar a que la foto se abra
        return True
    except TimeoutException:
        print(f"❌ No se encontró la miniatura de foto/video en {timeout} segundos.")
        return False
    except NoSuchElementException: 
        print(f"❌ La miniatura de foto/video en el índice no se encontró inmediatamente.")
        return False
    except Exception as e:
        print(f"❌ Error al intentar hacer clic en la miniatura de foto/video en el índice  {e}")
        return False




# --- Función Principal de Automatización con Mediciones de Ubicación ---
def test_instagram_automation():
    driver = None
    Red = None
    try:
        driver = setup_driver()
        Red = obtener_estado_conectividad_real(driver)
        if driver:
            print("\n--- Instagram Automation Started ---")
            
            # --- 1. Medición: Carga de App a For You Page ---
            lat_inicio_app_feed, lon_inicio_app_feed = get_device_location(driver)
            fecha_hora_inicio_app_feed = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            
            if measure_app_open_to_feed_time(driver):
                fecha_hora_fin_app_feed = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                guardar_resultado_y_tiempo_en_archivos(
                    METRICA_CARGA_APP_A_FEED, Red, lat_inicio_app_feed, lon_inicio_app_feed,
                    fecha_hora_inicio_app_feed, fecha_hora_fin_app_feed, "OK"
                )
            else:
                fecha_hora_fin_app_feed = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                guardar_resultado_y_tiempo_en_archivos(
                    METRICA_CARGA_APP_A_FEED, Red, lat_inicio_app_feed, lon_inicio_app_feed,
                    fecha_hora_inicio_app_feed, fecha_hora_fin_app_feed, "Fail"
                )
                print("⚠️ No se pudo medir el tiempo de carga del feed porque el feed no se detectó.")
                return

            # --- Proceso de Login (si es necesario) ---
            if not is_logged_in(driver):
                print("User is not logged in. Proceeding with login flow.")
            else:
                print("Skipping login process as user is already logged in.")
                time.sleep(2)

            # --- 2. Flujo de Publicación de Post ---
            click_tab_icon(driver, "com.instagram.android:id/tab_avatar", instance_index=0, description="Icono perfil (Avatar Tab)")
            click_tab_icon(driver, "com.instagram.android:id/tab_icon", instance_index=2, description="Icono crear (+) - Middle Tab Icon", timeout=10)
            print("✅ 'Crear (+)' icon clicked successfully.")
            
            if not asegurar_publicacion_activa(driver):
                print("❌ No se pudo asegurar la opción 'PUBLICACIÓN'. Abortando publicación.")
                return

            
            #select_from_grid(driver,3)
            random_photo(driver, PHOTO_THUMBNAIL_LOCATORS)
            click_button(driver, "com.instagram.android:id/next_button_textview", "Botón Siguiente (Selección de Media)")
            click_button(driver, "com.instagram.android:id/creation_next_button", "Botón Next creación")
            
            lat_inicio_post, lon_inicio_post = get_device_location(driver)
            fecha_hora_inicio_post = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print("\n⏱️ Medición: Tiempo de publicación del post...")
            
            if click_button(driver, "com.instagram.android:id/share_footer_button", "Botón Compartir publicación"):
                try:
                    WebDriverWait(driver, 90).until(
                        EC.any_of(
                            EC.invisibility_of_element_located((AppiumBy.XPATH, "//*[contains(@text, 'Finalizando') or contains(@text, 'Finishing')]")),
                            EC.invisibility_of_element_located((AppiumBy.XPATH, "//*[contains(@text, 'Compartiendo') or contains(@text, 'Sharing')]")),
                            EC.element_to_be_clickable((AppiumBy.ID, "com.instagram.android:id/feed_tab_icon"))
                        )
                    )
                    
                    fecha_hora_fin_post = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    print(f"✅ Publicación completada y confirmada.")
                    guardar_resultado_y_tiempo_en_archivos(
                        METRICA_PUBLICACION_POST, Red, lat_inicio_post, lon_inicio_post,
                        fecha_hora_inicio_post, fecha_hora_fin_post, "OK"
                    )
                except TimeoutException:
                    
                    fecha_hora_fin_post = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    print(f"⚠️ No se pudo confirmar la finalización de la publicación en 90s (timeout).")
                    guardar_resultado_y_tiempo_en_archivos(
                        METRICA_PUBLICACION_POST, Red, lat_inicio_post, lon_inicio_post,
                        fecha_hora_inicio_post, fecha_hora_fin_post, "Fail"
                    )
            else:
                
                fecha_hora_fin_post = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                guardar_resultado_y_tiempo_en_archivos(
                    METRICA_PUBLICACION_POST, Red, lat_inicio_post, lon_inicio_post,
                    fecha_hora_inicio_post, fecha_hora_fin_post, "Fail"
                )
                print("❌ No se pudo hacer clic en Compartir, no se medirá el tiempo de publicación.")

            # --- 3. Flujo de Mensaje de Texto ---
            time.sleep(2)
            click_button(driver, "com.instagram.android:id/action_bar_inbox_button", "Botón Inbox (Mensajes)")
            click_button(driver, "com.instagram.android:id/row_inbox_container", "Entrar al Primer Chat")

            lat_inicio_msg_texto, lon_inicio_msg_texto = get_device_location(driver)
            fecha_hora_inicio_msg_texto = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print("\n⏱️ Medición: Tiempo de envío de mensaje de texto...")

            if enter_text_ui(driver, 'new UiSelector().resourceId("com.instagram.android:id/row_thread_composer_edittext")', "Hola prueba", "Escribir un hola"):
                if click_button(driver, "com.instagram.android:id/row_thread_composer_send_button_container","Enviar mensaje", mandatory=False, timeout=7):
                    try:
                        print("🔍 Esperando desaparición de 'action_icon' o spinner para confirmar envío de texto...")
                        WebDriverWait(driver, 30).until(
                            EC.invisibility_of_element_located((AppiumBy.ID, "com.instagram.android:id/action_icon"))
                        )
                        
                        fecha_hora_fin_msg_texto = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                        print(f"✅ Mensaje de texto enviado y confirmado.")
                        guardar_resultado_y_tiempo_en_archivos(
                            METRICA_ENVIO_MSG_TEXTO, Red, lat_inicio_msg_texto, lon_inicio_msg_texto,
                            fecha_hora_inicio_msg_texto, fecha_hora_fin_msg_texto, "OK"
                        )
                    except TimeoutException:
                        
                        fecha_hora_fin_msg_texto = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                        print(f"⚠️ No se pudo confirmar el envío del mensaje de texto en 30s (timeout).")
                        guardar_resultado_y_tiempo_en_archivos(
                            METRICA_ENVIO_MSG_TEXTO, Red, lat_inicio_msg_texto, lon_inicio_msg_texto,
                            fecha_hora_inicio_msg_texto, fecha_hora_fin_msg_texto, "Fail"
                        )
                else:
                    
                    fecha_hora_fin_msg_texto = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    guardar_resultado_y_tiempo_en_archivos(
                        METRICA_ENVIO_MSG_TEXTO, Red, lat_inicio_msg_texto, lon_inicio_msg_texto,
                        fecha_hora_inicio_msg_texto, fecha_hora_fin_msg_texto, "Fail"
                    )
                    print("❌ No se pudo hacer clic en Enviar Mensaje, no se medirá el tiempo.")
            else:
                
                fecha_hora_fin_msg_texto = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                guardar_resultado_y_tiempo_en_archivos(
                    METRICA_ENVIO_MSG_TEXTO, Red, lat_inicio_msg_texto, lon_inicio_msg_texto,
                    fecha_hora_inicio_msg_texto, fecha_hora_fin_msg_texto, "Fail"
                )
                print("❌ No se pudo ingresar texto, no se medirá el tiempo de envío.")

            # --- 4. Flujo de Mensaje con Foto ---
            time.sleep(2)
            if click_button(driver, "com.instagram.android:id/row_thread_composer_button_gallery", "Botón Galería"):
                if select_from_gallery(driver, 2):
                    lat_inicio_msg_foto, lon_inicio_msg_foto = get_device_location(driver)
                    fecha_hora_inicio_msg_foto = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    print("\n⏱️ Medición: Tiempo de envío de mensaje con foto...")
                    
                    if click_button(driver, "com.instagram.android:id/media_thumbnail_tray_button","Enviar foto", mandatory=False, timeout=7):
                        try:
                            print("🔍 Esperando desaparición de 'action_icon' o spinner para confirmar envío de foto...")
                            WebDriverWait(driver, 60).until(
                                EC.invisibility_of_element_located((AppiumBy.ID, "com.instagram.android:id/action_icon"))
                            )
                            
                            fecha_hora_fin_msg_foto = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                            print(f"✅ Mensaje con foto enviado y confirmado.")
                            guardar_resultado_y_tiempo_en_archivos(
                                METRICA_ENVIO_MSG_FOTO, Red, lat_inicio_msg_foto, lon_inicio_msg_foto,
                                fecha_hora_inicio_msg_foto, fecha_hora_fin_msg_foto, "OK"
                            )
                        except TimeoutException:
                            
                            fecha_hora_fin_msg_foto = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                            print(f"⚠️ No se pudo confirmar el envío de la foto en 60s (timeout).")
                            guardar_resultado_y_tiempo_en_archivos(
                                METRICA_ENVIO_MSG_FOTO, Red, lat_inicio_msg_foto, lon_inicio_msg_foto,
                                fecha_hora_inicio_msg_foto, fecha_hora_fin_msg_foto, "Fail"
                            )
                    else:
                        
                        fecha_hora_fin_msg_foto = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                        guardar_resultado_y_tiempo_en_archivos(
                            METRICA_ENVIO_MSG_FOTO, Red, lat_inicio_msg_foto, lon_inicio_msg_foto,
                            fecha_hora_inicio_msg_foto, fecha_hora_fin_msg_foto, "Fail"
                        )
                        print(f"❌ No se pudo hacer clic en Enviar Foto Seleccionada, no se medirá el tiempo.")
                else:
                    
                    fecha_hora_fin_msg_foto = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    guardar_resultado_y_tiempo_en_archivos(
                        METRICA_ENVIO_MSG_FOTO, Red, lat_inicio_msg_foto, lon_inicio_msg_foto,
                        fecha_hora_inicio_msg_foto, fecha_hora_fin_msg_foto, "Fail"
                    )
                    print("❌ No se pudo seleccionar una foto de la galería del chat.")
            else:
                
                fecha_hora_fin_msg_foto = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                guardar_resultado_y_tiempo_en_archivos(
                    METRICA_ENVIO_MSG_FOTO, Red, lat_inicio_msg_foto, lon_inicio_msg_foto,
                    fecha_hora_inicio_msg_foto, fecha_hora_fin_msg_foto, "Fail"
                )
                print("❌ No se pudo hacer clic en el botón de Galería en el chat.")

            print("\n✅ Flujo principal de acciones completado.")

            time.sleep(2)


                        # --- 5. Flujo de Mensaje con Video ---
            time.sleep(2)
            if click_button(driver, "com.instagram.android:id/row_thread_composer_button_gallery", "Botón Galería"):
                if select_from_gallery(driver, 0):
                    lat_inicio_msg_foto, lon_inicio_msg_foto = get_device_location(driver)
                    fecha_hora_inicio_msg_foto = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    print("\n⏱️ Medición: Tiempo de envío de mensaje con Video...")
                    
                    if click_button(driver, "com.instagram.android:id/media_thumbnail_tray_button","Enviar Video", mandatory=False, timeout=7):
                        try:
                            print("🔍 Esperando desaparición de 'action_icon' o spinner para confirmar envío de Video...")
                            time.sleep(3)
                            WebDriverWait(driver, 60).until(
                                EC.invisibility_of_element_located((AppiumBy.ID, "com.instagram.android:id/action_icon"))
                            )
                           
                            fecha_hora_fin_msg_foto = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                            print(f"✅ Mensaje con foto enviado y confirmado.")
                            guardar_resultado_y_tiempo_en_archivos(
                                METRICA_ENVIO_MSG_VIDEO, Red, lat_inicio_msg_foto, lon_inicio_msg_foto,
                                fecha_hora_inicio_msg_foto, fecha_hora_fin_msg_foto, "OK"
                            )
                        except TimeoutException:
                           
                            fecha_hora_fin_msg_foto = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                            print(f"⚠️ No se pudo confirmar el envío de la foto en 60s (timeout).")
                            guardar_resultado_y_tiempo_en_archivos(
                                METRICA_ENVIO_MSG_VIDEO, Red, lat_inicio_msg_foto, lon_inicio_msg_foto,
                                fecha_hora_inicio_msg_foto, fecha_hora_fin_msg_foto, "Fail"
                            )
                    else:
                        
                        fecha_hora_fin_msg_foto = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                        guardar_resultado_y_tiempo_en_archivos(
                            METRICA_ENVIO_MSG_VIDEO, Red, lat_inicio_msg_foto, lon_inicio_msg_foto,
                            fecha_hora_inicio_msg_foto, fecha_hora_fin_msg_foto, "Fail"
                        )
                        print(f"❌ No se pudo hacer clic en Enviar Foto Seleccionada, no se medirá el tiempo.")
                else:
                   
                    fecha_hora_fin_msg_foto = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    guardar_resultado_y_tiempo_en_archivos(
                        METRICA_ENVIO_MSG_VIDEO, Red, lat_inicio_msg_foto, lon_inicio_msg_foto,
                        fecha_hora_inicio_msg_foto, fecha_hora_fin_msg_foto, "Fail"
                    )
                    print("❌ No se pudo seleccionar una foto de la galería del chat.")
            else:
                
                fecha_hora_fin_msg_foto = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                guardar_resultado_y_tiempo_en_archivos(
                    METRICA_ENVIO_MSG_VIDEO, Red, lat_inicio_msg_foto, lon_inicio_msg_foto,
                    fecha_hora_inicio_msg_foto, fecha_hora_fin_msg_foto, "Fail"
                )
                print("❌ No se pudo hacer clic en el botón de Galería en el chat.")

            print("\n✅ Flujo principal de acciones completado.")

            time.sleep(2)

    except Exception as e:
        print(f"❌ An error occurred during the test: {e}")
        if driver:
            timestamp_error = datetime.now().strftime("%Y%m%d_%H%M%S")
            error_screenshot_filename = f"error_general_test_{timestamp_error}.png"
            try:
                driver.save_screenshot(error_screenshot_filename)
                print(f"Screenshot saved as '{error_screenshot_filename}'.")
            except Exception as e_screenshot:
                print(f"Failed to save screenshot: {e_screenshot}")
    finally:
        print("\n--- Automation Finished ---")
        if driver:
            driver.quit()
            print("Driver quit.")


if __name__ == "__main__":


    csv_file_path = "metricas_instagram.csv"

    # Crear archivo si no existe o está vacío
    if not os.path.isfile(csv_file_path) or os.path.getsize(csv_file_path) == 0:
        with open(csv_file_path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow([
                "Instagram", "Tipo de test", "Ret", "Latitud", "Longitud",
                "Fecha_Hora_Inicio", "Fecha_Hora_Fin", "Comentario"
            ])
        print(f"📄 Archivo '{csv_file_path}' creado/inicializado con cabecera.")

    # Número de repeticiones
    
    repeticiones = 2

    for i in range(repeticiones):
        print(f"\n🔁 Ejecutando iteración {i + 1} de {repeticiones}...")
        try:
            test_instagram_automation()
        except Exception as e:
            print(f"❌ Error en la iteración {i + 1}: {e}")