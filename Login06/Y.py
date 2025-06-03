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
METRICA_CARGA_APP_A_FEED = "Tiempo Carga App a For You Page"
METRICA_PUBLICACION_POST = "Tiempo Publicación de Post"
METRICA_ENVIO_MSG_TEXTO = "Tiempo Envío Mensaje de Texto"
METRICA_ENVIO_MSG_FOTO = "Tiempo Envío Mensaje con Foto"

def setup_driver():
    desired_caps = {
        "platformName": "Android",
        "deviceName": "R58M795NHZF",
        "appPackage": "com.instagram.android",
        "appActivity": "com.instagram.android.activity.MainTabActivity",
        "automationName": "UiAutomator2",
        "forceAppLaunch": True,
        "noReset": True,
        "newCommandTimeout": 360 # Aumentado un poco por si acaso
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

def guardar_tiempo_en_txt_y_csv(segundos, nombre_metrica):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    csv_file_path = "tiempos_carga.csv"
    with open("tiempos_carga.txt", "a", encoding="utf-8") as txt_file:
        txt_file.write(f"{timestamp} - {nombre_metrica}: {segundos:.2f} segundos\n")
    file_exists = os.path.isfile(csv_file_path)
    is_empty = os.path.getsize(csv_file_path) == 0 if file_exists else True
    with open(csv_file_path, "a", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        if not file_exists or is_empty:
            writer.writerow(["Timestamp", "Metrica", "Duracion (segundos)"])
        writer.writerow([timestamp, nombre_metrica, round(segundos, 2)])
    print(f"📝 Tiempo guardado ({nombre_metrica}): {segundos:.2f}s en 'tiempos_carga.txt' y '{csv_file_path}'.")

def measure_app_open_to_feed_time(driver):
    print("\n⏱️ Medición: Tiempo desde apertura de app hasta carga del For You Page...")
    try:
        # Esperar a que cualquiera de estos elementos comunes del feed esté presente
        WebDriverWait(driver, 45).until(
            EC.any_of(
                EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/recycler_view")), # La lista de posts
                EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/refreshable_container")), # Contenedor común del feed
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
        time.sleep(1.5)
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
        time.sleep(1.5)
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
    """
    Encuentra múltiples elementos después de esperar un tiempo.
    Retorna una lista de elementos o una lista vacía.
    """
    try:
        print(f"Buscando '{description}'...")
        # Espera que al menos uno de los elementos esté presente antes de intentar encontrarlos todos
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

def random_photo(driver, thumbnail_locators): # Added parameters
    print("\n--- Intentando seleccionar una miniatura de foto aleatoriamente ---")
    photo_elements = []
    for by, value in thumbnail_locators: # Use the passed-in locators
        photo_elements = find_elements_safely(driver, by, value, timeout=10, description="Miniaturas de fotos")
        if photo_elements:
            break # Si encontramos elementos con un selector, salimos del bucle de selectores
            
    if photo_elements:
        random_photo = random.choice(photo_elements)
        # Intentar obtener el atributo 'content-desc' o 'text' para imprimirlo.
        photo_description = random_photo.get_attribute('content-desc') or random_photo.text or f"Elemento (Clase: {random_photo.tag_name})"
        print(f"✅ Seleccionando miniatura de foto aleatoria: '{photo_description}'")
        random_photo.click()
        print("✅ Clic en miniatura de foto exitoso.")
        time.sleep(2) # Esperar a que la foto se abra en pantalla completa
    else:
        raise Exception("❌ No se encontraron miniaturas de fotos para seleccionar con los selectores proporcionados.")

def asegurar_publicacion_activa(driver, timeout=5):
    print("\n🔍 Verificando si la opción 'PUBLICACIÓN' está activa...")

    try:
        # Intentar encontrar la opción activa con content-desc "PUBLICACIÓN"
        elemento_publicacion = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((
                AppiumBy.XPATH,
                '//android.widget.TextView[@content-desc="PUBLICACIÓN"]'
            ))
        )

        if elemento_publicacion.is_selected() or "selected" in (elemento_publicacion.get_attribute("selected") or ""):
            print("✅ Ya está seleccionada la opción 'PUBLICACIÓN'.")
            return True
        else:
            print("ℹ️ Opción 'PUBLICACIÓN' no está activa. Intentando activarla...")
            return click_button(driver, "com.instagram.android:id/cam_dest_feed", "Opción 'PUBLICACIÓN'")
    
    except Exception as e:
        print(f"❌ No se pudo verificar o seleccionar 'PUBLICACIÓN': {e}")
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

def test_instagram_automation():
    driver = None
    start_app_open_time = time.time()
    try:
        driver = setup_driver()
        if driver:
            print("\n--- Instagram Automation Started ---")
            # ... (medición de carga de app y login sin cambios) ...
            if measure_app_open_to_feed_time(driver):
                end_app_open_time = time.time()
                app_open_duration = end_app_open_time - start_app_open_time
                guardar_tiempo_en_txt_y_csv(app_open_duration, METRICA_CARGA_APP_A_FEED)
            else:
                print("⚠️ No se pudo medir el tiempo de carga del feed porque el feed no se detectó.")

            if not is_logged_in(driver):
                print("User is not logged in. Proceeding with login flow.")
                # ... (tu código de login aquí, asumiendo que funciona si es necesario) ...
            else:
                print("Skipping login process as user is already logged in.")
                time.sleep(2)

            click_tab_icon(driver, "com.instagram.android:id/tab_avatar", instance_index=0, description="Icono perfil (Avatar Tab)")
            click_tab_icon(driver, "com.instagram.android:id/tab_icon", instance_index=2, description="Icono crear (+) - Middle Tab Icon", timeout=10)
            print("✅ 'Crear (+)' icon clicked successfully.")
            asegurar_publicacion_activa(driver)
            random_photo(driver, PHOTO_THUMBNAIL_LOCATORS)
            click_button(driver, "com.instagram.android:id/next_button_textview", "Botón Siguiente (Selección de Media)")
            click_button(driver, "com.instagram.android:id/creation_next_button", "Botón Next creación")

            print("\n⏱️ Medición: Tiempo de publicación del post...")
            
            start_post_time = time.time()
            if click_button(driver, "com.instagram.android:id/share_footer_button", "Botón Compartir publicación"):
                try:
                    WebDriverWait(driver, 90).until(
                        EC.any_of(
                            EC.invisibility_of_element_located((AppiumBy.XPATH, "//*[contains(@text, 'Finalizando') or contains(@text, 'Finishing')]")),
                            EC.invisibility_of_element_located((AppiumBy.XPATH, "//*[contains(@text, 'Compartiendo') or contains(@text, 'Sharing')]")),
                            EC.invisibility_of_element_located((AppiumBy.ID, "com.instagram.android:id/next_button_textview")),
                            EC.element_to_be_clickable((AppiumBy.ID, "com.instagram.android:id/feed_tab_icon"))
                        )
                    )
                    end_post_time = time.time()
                    post_duration = end_post_time - start_post_time
                    print(f"✅ Publicación completada en {post_duration:.2f} segundos.")
                    guardar_tiempo_en_txt_y_csv(post_duration, METRICA_PUBLICACION_POST)
                except TimeoutException:
                    end_post_time = time.time() 
                    post_duration = end_post_time - start_post_time
                    print(f"⚠️ No se pudo confirmar la finalización de la publicación en 90s. Tiempo registrado: {post_duration:.2f}s.")
                    guardar_tiempo_en_txt_y_csv(post_duration, f"{METRICA_PUBLICACION_POST} (Timeout)")
            else:
                print("❌ No se pudo hacer clic en Compartir, no se medirá el tiempo de publicación.")


            time.sleep(2)
            click_button(driver, "com.instagram.android:id/action_bar_inbox_button", "Botón Inbox (Mensajes)")
            click_button(driver, "com.instagram.android:id/row_inbox_container", "Entrar al Primer Chat")

            if enter_text_ui(driver, 'new UiSelector().resourceId("com.instagram.android:id/row_thread_composer_edittext")', "Hola prueba", "Escribir un hola"):
                print("\n⏱️ Medición: Tiempo de envío de mensaje de texto...")
                start_send_text_time = time.time()
                send_button_clicked = False
                if click_button(driver, "com.instagram.android:id/row_thread_composer_send_button_container","Enviar mensaje",mandatory=False, timeout=7):
                    send_button_clicked = True
                
                if send_button_clicked:
                    try:
                        print("🔍 Esperando desaparición de 'action_icon' para confirmar envío de texto...")
                        WebDriverWait(driver, 30).until(
                            EC.invisibility_of_element_located((AppiumBy.ID, "com.instagram.android:id/action_icon"))
                        )
                        end_send_text_time = time.time()
                        send_text_duration = end_send_text_time - start_send_text_time
                        print(f"✅ Mensaje de texto enviado (action_icon desapareció) en {send_text_duration:.2f} segundos.")
                        guardar_tiempo_en_txt_y_csv(send_text_duration, METRICA_ENVIO_MSG_TEXTO)
                    except TimeoutException:
                        end_send_text_time = time.time()
                        send_text_duration = end_send_text_time - start_send_text_time
                        print(f"⚠️ No se pudo confirmar desaparición de 'action_icon' para texto en 30s. Tiempo: {send_text_duration:.2f}s.")
                        guardar_tiempo_en_txt_y_csv(send_text_duration, f"{METRICA_ENVIO_MSG_TEXTO} (Timeout por action_icon)")
                else:
                    print("❌ No se pudo hacer clic en Enviar Mensaje, no se medirá el tiempo.")

            time.sleep(2)
               
            if click_button(driver, "com.instagram.android:id/row_thread_composer_button_gallery", "Botón Galería"):
                if select_from_gallery(driver, 2):
                    print("\n⏱️ Medición: Tiempo de envío de mensaje con foto...")
                    start_send_photo_time = time.time()
                    photo_sent_clicked = False
                    
                    if click_button(driver, "com.instagram.android:id/media_thumbnail_tray_button","enviar foto", mandatory=False, timeout=7):
                        photo_sent_clicked = True

                    if photo_sent_clicked:
                        try:
                            print("🔍 Esperando desaparición de 'action_icon' para confirmar envío de foto...")
                            WebDriverWait(driver, 60).until(
                                EC.invisibility_of_element_located((AppiumBy.ID, "com.instagram.android:id/action_icon"))
                            )
                            end_send_photo_time = time.time()
                            send_photo_duration = end_send_photo_time - start_send_photo_time
                            print(f"✅ Mensaje con foto enviado (action_icon desapareció) en {send_photo_duration:.2f} segundos.")
                            guardar_tiempo_en_txt_y_csv(send_photo_duration, METRICA_ENVIO_MSG_FOTO)
                        except TimeoutException:
                            end_send_photo_time = time.time()
                            send_photo_duration = end_send_photo_time - start_send_photo_time
                            print(f"⚠️ No se pudo confirmar desaparición de 'action_icon' para foto en 60s. Tiempo: {send_photo_duration:.2f}s.")
                            guardar_tiempo_en_txt_y_csv(send_photo_duration, f"{METRICA_ENVIO_MSG_FOTO} (Timeout por action_icon)")
                    else:
                        print(f"❌ No se pudo hacer clic en Enviar Foto Seleccionada, no se medirá el tiempo.")
                else:
                    print("❌ No se pudo seleccionar una foto de la galería del chat.")
            else:
                print("❌ No se pudo hacer clic en el botón de Galería en el chat.")

            print("\n✅ Flujo principal de acciones completado.")
            time.sleep(5)

    except Exception as e:
        print(f"❌ An error occurred during the test: {e}")
        # ... (manejo de excepciones y finally sin cambios) ...
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
    csv_file_path = "tiempos_carga.csv"
    if not os.path.isfile(csv_file_path) or os.path.getsize(csv_file_path) == 0:
        with open(csv_file_path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(["Timestamp", "Metrica", "Duracion (segundos)"])
        print(f"Archivo '{csv_file_path}' creado/inicializado con cabecera.")
    
    test_instagram_automation()