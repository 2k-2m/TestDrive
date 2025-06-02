from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from appium.webdriver.extensions.android.nativekey import AndroidKey # Para la tecla BACK
import time

# --- Constantes para Selectores (AJUSTAR SEGÚN SEA NECESARIO) ---
# General
USER_FIELD_SELECTOR = 'new UiSelector().className("android.widget.EditText").instance(0)'
PASS_FIELD_SELECTOR = 'new UiSelector().className("android.widget.EditText").instance(1)'
LOGIN_BUTTON_XPATH = '//android.widget.Button[@content-desc="Log in"]' # Ajustado para usar @content-desc
FACEBOOK_LOGO_ACCESSIBILITY_ID = "Facebook logo" # O un selector más robusto para la pantalla principal

# Pop-ups comunes
# Selectores para "No guardar información"
POPUP_SAVE_LOGIN_INFO_NOT_NOW_XPATH = "//android.widget.Button[@text='Not Now']" # O texto similar
POPUP_SAVE_LOGIN_INFO_NO_XPATH = "//android.widget.Button[@text='NO']" # También puede aparecer "NO"

# Pop-ups de notificaciones y otros permisos del OS/Facebook
POPUP_TURN_ON_NOTIFICATIONS_DENY_XPATH = "//android.widget.Button[contains(@text, 'Deny') or contains(@text, 'DENY') or contains(@text, 'Don’t allow') or contains(@content-desc, 'Don’t Allow')]"
OS_PERMISSION_DENY_BUTTON_ID = "com.android.permissioncontroller:id/permission_deny_button"
OS_PERMISSION_ALLOW_BUTTON_ID = "com.android.permissioncontroller:id/permission_allow_button" # Mantenerlo por si acaso, pero lo denegaremos por defecto.

# Crear Publicación / Subir Imagen
CREATE_POST_FIELD_XPATH = "//*[contains(@content-desc, 'What’s on your mind') or contains(@text, 'What’s on your mind')]" # Campo para iniciar una publicación
PHOTO_VIDEO_BUTTON_ACCESSIBILITY_ID = "Photo/Video" # Botón para añadir foto/video. Puede variar.
FIRST_GALLERY_IMAGE_XPATH = "(//android.view.ViewGroup[contains(@content-desc, 'Photo') or contains(@content-desc, 'Image')])[1]/android.widget.ImageView" # Primer imagen en la galería. MUY PROPENSO A CAMBIOS.
POST_BUTTON_ACCESSIBILITY_ID = "POST" # Botón para publicar.

# Visualizar Video
VIDEO_PLAY_BUTTON_XPATH = "(//*[contains(@content-desc, 'Play video') or contains(@content-desc, 'Video status')])[1]" # Trata de encontrar un botón de play o indicador de video

# Reaccionar a Publicación
LIKE_BUTTON_XPATH = "(//*[contains(@content-desc, 'Like button') or contains(@content-desc, 'Like')])[1]" # Primer botón de "Me gusta". Puede necesitar ser más específico.

# --- Funciones Auxiliares ---

def handle_optional_element_click(driver, wait, by, value, timeout=5, description="Elemento opcional"):
    """Intenta hacer clic en un elemento si aparece. Devuelve True si se hizo clic, False en caso contrario."""
    try:
        element = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))
        if element.is_displayed():
            element.click()
            print(f"Se hizo clic en '{description}'.")
            return True
    except TimeoutException:
        print(f"'{description}' no apareció o no fue interactuable en {timeout} segundos.")
    except Exception as e:
        print(f"Error al interactuar con '{description}': {e}")
    return False

def scroll_down(driver, duration=500):
    """Realiza un scroll hacia abajo en la pantalla."""
    size = driver.get_window_size()
    start_x = size['width'] // 2
    start_y = int(size['height'] * 0.8)
    end_y = int(size['height'] * 0.2)
    try:
        driver.swipe(start_x, start_y, start_x, end_y, duration)
        print("Scroll hacia abajo realizado.")
        time.sleep(2) # Espera para que cargue el contenido
    except Exception as e:
        print(f"Error durante el scroll: {e}")

# --- Script Principal ---

def test_facebook_actions():
    desired_caps = {
        "platformName": "Android",
        "deviceName": "emulator-5554",
        "appPackage": "com.facebook.katana",
        "appActivity": "com.facebook.katana.LoginActivity",
        "automationName": "UiAutomator2",
        "noReset": False, # Para una prueba limpia, False. Esto asegura que la app se resetee.
        "fullReset": False,
        "unlockType": "pin",
        "unlockKey": "1234"
    }

    options = UiAutomator2Options().load_capabilities(desired_caps)
    driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
    wait = WebDriverWait(driver, 45)
    short_wait = WebDriverWait(driver, 10)

    try:
        print("Iniciando prueba de Facebook...")

        # --- ETAPA DE LOGIN ---
        print("Intentando iniciar sesión...")
        # Ingresar usuario
        user_field = wait.until(EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, USER_FIELD_SELECTOR)))
        user_field.clear()
        user_field.send_keys("drivetestviva2025@gmail.com")
        print("Usuario ingresado.")

        # Ingresar contraseña
        password_field = wait.until(EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, PASS_FIELD_SELECTOR)))
        password_field.clear()
        password_field.send_keys("drivetestviv@2025_face")
        print("Contraseña ingresada.")

        # Clic en login
        login_button = wait.until(EC.element_to_be_clickable((AppiumBy.XPATH, LOGIN_BUTTON_XPATH)))
        login_button.click()
        print("Clic en botón de Login.")

        # --- MANEJO DE POP-UPS POST-LOGIN INICIAL ---
        # Priorizar "NO" o "Not Now" para no guardar la información de inicio de sesión
        time.sleep(5) # Espera inicial para que carguen popups

        print("Manejando pop-ups de guardar información y permisos...")
        # Pop-up: "Guardar información de inicio de sesión?" o "Mantener sesión iniciada?"
        # Intentar "Not Now" primero, si no, buscar "NO".
        if not handle_optional_element_click(driver, short_wait, AppiumBy.XPATH, POPUP_SAVE_LOGIN_INFO_NOT_NOW_XPATH, description="Popup 'Guardar Info - Not Now'"):
            handle_optional_element_click(driver, short_wait, AppiumBy.XPATH, POPUP_SAVE_LOGIN_INFO_NO_XPATH, description="Popup 'Guardar Info - NO'")
        
        # Pop-up de permisos de notificación del OS (siempre denegar para no guardar información)
        handle_optional_element_click(driver, short_wait, AppiumBy.ID, OS_PERMISSION_DENY_BUTTON_ID, description="OS Permission 'Deny Notifications'")

        # Pop-up de Facebook para activar notificaciones (siempre denegar)
        handle_optional_element_click(driver, short_wait, AppiumBy.XPATH, POPUP_TURN_ON_NOTIFICATIONS_DENY_XPATH, description="Facebook 'Turn on Notifications - Deny'")

        # Otros pop-ups generales de "Don't allow"
        handle_optional_element_click(driver, short_wait, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Don’t allow")', description="Facebook 'Don’t allow'")
        handle_optional_element_click(driver, short_wait, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Now Not")', description="Facebook 'Now Not'") # Otra variante de "Ahora no"
        handle_optional_element_click(driver, short_wait, AppiumBy.XPATH, "//android.widget.Button[contains(@text, 'CONTINUAR') or contains(@text, 'Continue')]", description="Botón 'Continuar' (si hay)")
        
        # Si después de manejar los pop-ups, hay un botón de "Aceptar" genérico, lo pulsamos (con precaución)
        handle_optional_element_click(driver, short_wait, AppiumBy.XPATH, "//*[contains(@text, 'Aceptar') or contains(@text, 'Accept')]", description="Botón 'Aceptar' genérico")


        # Validación de acceso correcto (esperar a que cargue la pantalla principal)
        try:
            WebDriverWait(driver, 20).until(
                EC.any_of(
                    EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, FACEBOOK_LOGO_ACCESSIBILITY_ID)),
                    EC.presence_of_element_located((AppiumBy.XPATH, CREATE_POST_FIELD_XPATH))
                )
            )
            print("Login exitoso: Pantalla principal de Facebook detectada.")
        except TimeoutException:
            print("No se pudo verificar el login exitoso (logo o campo de post no encontrado).")
            raise

        time.sleep(5)

        # --- ETAPA 1: SUBIR UNA IMAGEN ---
        print("\n--- Iniciando subida de imagen ---")
        try:
            create_post_field = wait.until(EC.element_to_be_clickable((AppiumBy.XPATH, CREATE_POST_FIELD_XPATH)))
            create_post_field.click()
            print("Clic en 'What's on your mind?'.")
            time.sleep(2)

            photo_video_button = wait.until(EC.element_to_be_clickable((AppiumBy.ACCESSIBILITY_ID, PHOTO_VIDEO_BUTTON_ACCESSIBILITY_ID)))
            photo_video_button.click()
            print("Clic en botón 'Photo/Video'.")
            time.sleep(2)

            # Manejar permiso de acceso a medios (DENY por defecto para el ejercicio, aunque para subir imagen necesitarías ALLOW)
            # Para este escenario de "siempre pedir contraseña", vamos a denegar todos los permisos opcionales.
            # Si necesitas subir una imagen, deberías cambiar esto a ALLOW.
            if handle_optional_element_click(driver, short_wait, AppiumBy.ID, OS_PERMISSION_DENY_BUTTON_ID, description="OS Permission 'Deny media access'"):
                print("Se denegó el acceso a medios. No se podrá subir la imagen.")
                # Si se denegó el permiso, es posible que no se pueda continuar con la subida.
                # Puedes agregar un `raise` o un `return` aquí para detener la prueba si este paso es crítico.
                # O puedes implementar una lógica para "volver" si se denegó el permiso y continuar con otras acciones.
                driver.press_keycode(AndroidKey.BACK) # Volver de la pantalla de permisos
                time.sleep(1)
                driver.press_keycode(AndroidKey.BACK) # Volver de la pantalla de selección de imagen
                time.sleep(1)
                raise Exception("Acceso a medios denegado, omitiendo subida de imagen.")
            else:
                # Si el permiso no apareció o no se denegó, intentamos continuar con la selección de imagen.
                # Si el permiso es crucial y no se concedió, esta parte fallaría.
                print("Permiso de acceso a medios no apareció o no se pudo denegar. Intentando seleccionar imagen...")
                # 4. Seleccionar la primera imagen de la galería
                first_image = wait.until(EC.element_to_be_clickable((AppiumBy.XPATH, FIRST_GALLERY_IMAGE_XPATH)))
                first_image.click()
                print("Primera imagen de la galería seleccionada.")
                time.sleep(2)

                # 6. Clic en el botón "Post"
                post_button = wait.until(EC.element_to_be_clickable((AppiumBy.ACCESSIBILITY_ID, POST_BUTTON_ACCESSIBILITY_ID)))
                post_button.click()
                print("Clic en botón 'Post'.")
                print("Esperando a que la imagen se suba (aprox 20 segundos)...")
                time.sleep(20)
                print("Subida de imagen completada (asumido).")

        except Exception as e:
            print(f"Error durante la subida de imagen: {e}")
            driver.press_keycode(AndroidKey.BACK)
            time.sleep(1)
            driver.press_keycode(AndroidKey.BACK)
            time.sleep(1)

        # --- ETAPA 2: VISUALIZAR UN VIDEO ---
        print("\n--- Iniciando visualización de video ---")
        video_found_and_played = False
        try:
            for _ in range(3):
                try:
                    video_element = short_wait.until(EC.presence_of_element_located((AppiumBy.XPATH, VIDEO_PLAY_BUTTON_XPATH)))
                    if video_element.is_displayed():
                        print("Video encontrado en el feed.")
                        video_element.click()
                        print("Video clickeado. Visualizando por 10 segundos...")
                        time.sleep(10)
                        
                        print("Presionando BACK para cerrar el video (si está en pantalla completa).")
                        driver.press_keycode(AndroidKey.BACK)
                        time.sleep(2)
                        video_found_and_played = True
                        break
                except TimeoutException:
                    print("No se encontró un video en la vista actual. Scrolleando...")
                    scroll_down(driver)
            
            if not video_found_and_played:
                print("No se pudo encontrar un video para visualizar después de varios intentos.")

        except Exception as e:
            print(f"Error durante la visualización de video: {e}")
            driver.press_keycode(AndroidKey.BACK)
            time.sleep(1)

        print("Intentando volver al tope del feed...")
        for _ in range(2):
            size = driver.get_window_size()
            start_x = size['width'] // 2
            start_y = int(size['height'] * 0.2)
            end_y = int(size['height'] * 0.8)
            driver.swipe(start_x, start_y, start_x, end_y, 400)
            time.sleep(1)
        time.sleep(3)

        # --- ETAPA 3: REACCIONAR A LA PRIMERA PUBLICACIÓN ---
        print("\n--- Iniciando reacción a la primera publicación ---")
        try:
            like_button = wait.until(EC.element_to_be_clickable((AppiumBy.XPATH, LIKE_BUTTON_XPATH)))
            like_button.click()
            print("Se hizo clic en 'Me gusta' en la primera publicación encontrada.")
            time.sleep(3)
        except Exception as e:
            print(f"Error al reaccionar a la publicación: {e}")

        print("\nTodas las acciones completadas.")

    except TimeoutException as te:
        print(f"TimeoutException general: {te}")
    except Exception as e:
        print(f"Ocurrió un error inesperado: {e}")
    finally:
        print("Finalizando prueba.")
        time.sleep(5)
        if driver:
            driver.quit()

if __name__ == "__main__":
    test_facebook_actions()