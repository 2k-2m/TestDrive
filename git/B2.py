from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import random 

# --- Funciones de Utilidad ---
def wait_and_click(driver, by, value, timeout=10, description="Elemento"):
    """
    Espera hasta que un elemento sea clicable y le da click.
    Imprime mensajes para depuración.
    """
    try:
        print(f"Intentando hacer clic en '{description}' (By: {by}, Value: '{value}')...")
        element = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, value)))
        time.sleep(0.5) # Pequeña pausa por si el elemento necesita estabilizarse
        element.click()
        print(f"✅ Clic exitoso en '{description}'.")
        return True
    except TimeoutException:
        print(f"❌ '{description}' no fue encontrado o clicable en {timeout} segundos.")
        return False
    except Exception as e:
        print(f"❌ Error al intentar clicar '{description}': {e}")
        return False

def wait_for_presence(driver, by, value, timeout=10, description="Elemento"):
    """
    Espera hasta que un elemento esté presente en el DOM.
    Imprime mensajes para depuración.
    """
    try:
        print(f"Esperando la presencia de '{description}' (By: {by}, Value: '{value}')...")
        element = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))
        print(f"✅ '{description}' encontrado.")
        return element
    except TimeoutException:
        print(f"❌ '{description}' no apareció en {timeout} segundos.")
        return None
    except Exception as e:
        print(f"❌ Error al esperar la presencia de '{description}': {e}")
        return None

def find_elements_safely(driver, by, value, timeout=10, description="Elementos"):
    """
    Encuentra múltiples elementos después de esperar un tiempo.
    Retorna una lista de elementos o una lista vacía.
    """
    try:
        print(f"Buscando '{description}' (By: {by}, Value: '{value}')...")
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

# --- Selectores de Elementos de la UI ---
POPUP_DENY_LOCATORS = [
    # El selector principal que ha demostrado funcionar para "Not now" / "Ahora no"
    (AppiumBy.XPATH, "//*[contains(@text, 'Not now') or contains(@text, 'Ahora no')]"), 
    
    # Selectores de respaldo para pop-ups genéricos de Android o Instagram
    # (ej. "Guardar información de login", permisos de acceso)
    (AppiumBy.ID, "android:id/button2"), # Usado a menudo para "Ahora no" de guardar contraseña
    (AppiumBy.ID, "com.android.permissioncontroller:id/permission_deny_button"), # Para denegar permisos
]

CONTINUE_BUTTON_LOCATORS = [
    (AppiumBy.XPATH, '//android.widget.Button[@content-desc="Continue"]/android.view.ViewGroup'), 
    (AppiumBy.ACCESSIBILITY_ID, "Continue"),
    (AppiumBy.XPATH, '//*[contains(@text, "Continue") or contains(@content-desc, "Continue")]'),
]

AVATAR_LOCATORS = [
    (AppiumBy.ID, "com.instagram.android:id/tab_avatar"),
    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().resourceId("com.instagram.android:id/tab_avatar")'),
    (AppiumBy.XPATH, '//android.widget.ImageView[@resource-id="com.instagram.android:id/tab_avatar"]'),
]

POST_TAB_ICON_LOCATORS = [
    # Selector para el icono de publicaciones (el tercer tab_icon, si contamos desde 0)
    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().resourceId("com.instagram.android:id/tab_icon").instance(2)'), 
    (AppiumBy.XPATH, '(//android.widget.ImageView[@resource-id="com.instagram.android:id/tab_icon"])[3]'), 
]

MAIN_PAGE_VALIDATION_LOCATORS = [
    # EL SELECTOR DE "INICIO" YA FUNCIONA PARA VALIDAR LA PÁGINA PRINCIPAL.
    # Si encuentras otros más robustos o necesarios con Appium Inspector, añádelos aquí.
    (AppiumBy.XPATH, '//android.widget.FrameLayout[@content-desc="Inicio" or @content-desc="Home"]'), 
    
    # Ejemplos de otros selectores que podrías haber encontrado y no funcionaron o son menos fiables:
    # (AppiumBy.ID, "com.instagram.android:id/action_bar_title"), 
    # (AppiumBy.XPATH, '//android.widget.ImageView[@content-desc="Instagram"]'), 
    # (AppiumBy.XPATH, '//android.widget.FrameLayout[@content-desc="Perfil" or @content-desc="Profile"]'), 
    # (AppiumBy.XPATH, '//android.widget.ImageView[@content-desc="Cámara"]'), 
]

PHOTO_THUMBNAIL_LOCATORS = [
    # **SELECTOR ROBUSTO:** Busca Buttons (miniaturas) dentro del GridView principal de fotos
    # Este es el selector más fiable que hemos identificado con tu última información.
    (AppiumBy.XPATH, '//android.widget.GridView[@resource-id="com.instagram.android:id/media_picker_grid_view"]//android.widget.Button'),
    
    # Alternativa UiAutomator2 (equivalente al XPath anterior)
    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().resourceId("com.instagram.android:id/media_picker_grid_view").childSelector(new UiSelector().className("android.widget.Button"))'),
    
    # Respaldo genérico (menos específico pero podría funcionar si los otros fallan inesperadamente)
    (AppiumBy.CLASS_NAME, "android.widget.Button"),
]

NEXT_BUTTON_LOCATORS = [
    (AppiumBy.ID, "com.instagram.android:id/next_button_textview"),
    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().resourceId("com.instagram.android:id/next_button_textview")'),
    (AppiumBy.XPATH, '//android.widget.Button[@content-desc="Next"]'),
]


# --- Función para Manejar Pop-ups ---
def handle_instagram_popups(driver):
    """
    Intenta cerrar cualquier pop-up que pueda aparecer.
    Optimizada para ser más eficiente al reintentar selectores.
    """
    print("\n--- Manejando posibles Pop-ups de Instagram ---")
    popups_handled_count = 0
    
    # Intentar varias rondas para cerrar pop-ups, ya que uno puede revelar otro.
    # Limitamos a 5 rondas para evitar bucles infinitos.
    for i in range(5): 
        popup_found_and_clicked_in_this_round = False
        for by, value in POPUP_DENY_LOCATORS:
            # Asignar un timeout más largo para el pop-up principal "Not now",
            # y más corto para los otros respaldos si aparecen.
            current_timeout = 5 if (by == AppiumBy.XPATH and "Not now" in value) else 3 

            if wait_and_click(driver, by, value, timeout=current_timeout, description=f"Botón de Pop-up IG ({value})"):
                popup_found_and_clicked_in_this_round = True
                popups_handled_count += 1
                time.sleep(2) # Esperar un poco después de cerrar un pop-up para que la UI se estabilice
                # Si se clicó un pop-up, rompemos el bucle de selectores de la ronda actual
                # y volvemos a intentar desde el principio de la lista de pop-ups en la siguiente ronda.
                break 
        
        # Si en esta ronda no se encontró ni se clicó ningún pop-up, salimos del bucle principal.
        if not popup_found_and_clicked_in_this_round:
            break

    if popups_handled_count > 0:
        print(f"✅ Se manejaron {popups_handled_count} pop-ups de Instagram.")
    else:
        print("ℹ️ No se detectaron pop-ups conocidos de Instagram para manejar.")
    time.sleep(1) # Pequeña pausa final después de terminar de manejar pop-ups

# --- Función Principal de Prueba ---
def test_instagram_interaction():
    # --- Configuración de Capacidades Deseadas para Appium ---
    desired_caps = {
        "platformName": "Android",
        "deviceName": "emulator-5554",  # <--- ASEGÚRATE DE QUE ESTO COINCIDE CON TU EMULADOR/DISPOSITIVO
        "appPackage": "com.instagram.android",
        "appActivity": "com.instagram.android.activity.MainTabActivity",
        "automationName": "UiAutomator2",
        "autoGrantPermissions": True, # Concede permisos automáticamente
        "noReset": False, # No restablece la app entre sesiones (útil para mantener el login)
        "newCommandTimeout": 300, # Aumenta el timeout para comandos
       
    }

    options = UiAutomator2Options().load_capabilities(desired_caps)
    driver = None
    try:
        driver = webdriver.Remote("http://127.0.0.1:4723", options=options)

        print("Iniciando prueba de Instagram...")

        # --- Credenciales de Instagram (MANTENLAS SEGURAS) ---
        INSTAGRAM_USERNAME = "drivetest.2025.viva@gmail.com"
        INSTAGRAM_PASSWORD = "drivetestviv@2025_face"

        # --- Paso 1: Manejar la pantalla "Continue" si aparece ---
        continue_clicked = False
        print("Intentando hacer clic en el botón 'Continue' (si aparece)...")
        for by, value in CONTINUE_BUTTON_LOCATORS:
            if wait_and_click(driver, by, value, timeout=7, description=f"Botón 'Continue' ({value})"):
                print("✅ Clic en 'Continue' exitoso.")
                continue_clicked = True
                time.sleep(5) # Esperar a que la pantalla se estabilice después del clic
                break 
        
        if continue_clicked:
            print("Pantalla 'Continue' manejada. Procediendo con el flujo.")
        else:
            print("Pantalla 'Continue' no detectada o no se pudo hacer clic. Procediendo con login explícito (si fuera necesario).")

        # --- Paso 2: Login explícito (Solo si la pantalla 'Continue' no fue manejada) ---
        # Si la pantalla 'Continue' maneja el inicio de sesión automático, este paso se omite.
        if not continue_clicked:
            # Intentar encontrar y llenar el campo de usuario
            user_field = wait_for_presence(driver, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().className("android.widget.EditText").instance(0)', description="Campo de usuario")
            if user_field:
                user_field.clear()
                user_field.send_keys(INSTAGRAM_USERNAME)
                print(f"✅ Usuario '{INSTAGRAM_USERNAME}' ingresado.")
            else:
                raise Exception("❌ No se encontró el campo de usuario para login explícito.")

            # Intentar encontrar y llenar el campo de contraseña
            password_field = wait_for_presence(driver, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().className("android.widget.EditText").instance(1)', timeout=10, description="Campo de contraseña")
            if password_field:
                password_field.clear()
                password_field.send_keys(INSTAGRAM_PASSWORD)
                print("✅ Contraseña ingresada.")
            else:
                raise Exception("❌ No se encontró el campo de contraseña.")

            # Intentar hacer clic en el botón de login
            if not wait_and_click(driver, AppiumBy.XPATH, '//android.view.View[@content-desc="Log in"]', description="Botón de Log in"):
                 raise Exception("❌ No se pudo hacer clic en el botón de Log in.")
            print("✅ Clic en botón de Log in exitoso.")
            time.sleep(5) # Esperar a que la app procese el login
        else:
            print("Login explícito omitido ya que la pantalla 'Continue' fue manejada.")

        # --- Paso 3: Manejo de pop-ups post-login ---
        handle_instagram_popups(driver)

        # --- Paso 4: Validar que la página principal de Instagram sea visible ---
        print("\n--- Validando que la página principal de Instagram sea visible ---")
        main_page_visible = False
        for by, value in MAIN_PAGE_VALIDATION_LOCATORS:
            if wait_for_presence(driver, by, value, timeout=10, description=f"Elemento de página principal ({value})"):
                print(f"✅ Elemento '{value}' encontrado. Página principal visible.")
                main_page_visible = True
                break
        
        if not main_page_visible:
            raise Exception("❌ No se detectó ningún elemento clave de la página principal. Posiblemente hay un pop-up no manejado o la pantalla no cargó.")

        print("Esperando unos segundos en la página principal...")
        time.sleep(3) 

        # --- Paso 5: Hacer clic en el avatar (para ir al perfil) ---
        print("\n--- Intentando hacer clic en el avatar (perfil) ---")
        avatar_clicked = False
        for by, value in AVATAR_LOCATORS:
            if wait_and_click(driver, by, value, timeout=10, description=f"Avatar (Perfil) ({value})"):
                print("✅ Clic en el avatar (perfil) exitoso.")
                avatar_clicked = True
                time.sleep(5) # Esperar a que cargue la página de perfil
                break
        
        if not avatar_clicked:
            raise Exception("❌ No se pudo hacer clic en el avatar (botón de perfil).")

        print("Ahora estás en la página de perfil. Esperando unos segundos...")
        time.sleep(3)

        # --- Paso 6: Clic en el icono de publicaciones (tercer tab_icon, si no estás ya en la sección de publicaciones) ---
        print("\n--- Intentando hacer clic en el icono de publicaciones (tercer tab_icon) ---")
        post_tab_clicked = False
        for by, value in POST_TAB_ICON_LOCATORS:
            if wait_and_click(driver, by, value, timeout=10, description=f"Icono de Publicaciones ({value})"):
                print("✅ Clic en el icono de publicaciones exitoso.")
                post_tab_clicked = True
                time.sleep(3) # Dar tiempo para que se carguen las miniaturas si no estaban visibles
                break
        
        if not post_tab_clicked:
            print("ℹ️ No se pudo hacer clic en el icono de publicaciones, asumiendo que ya está en la vista correcta o no es necesario.")
            # No elevamos excepción aquí para permitir que el script continúe si ya está en la vista.

        # --- Paso 7: Seleccionar una imagen aleatoriamente de las miniaturas ---
        print("\n--- Intentando seleccionar una miniatura de foto aleatoriamente ---")
        photo_elements = []
        for by, value in PHOTO_THUMBNAIL_LOCATORS:
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
            time.sleep(5) # Esperar a que la foto se abra en pantalla completa
        else:
            raise Exception("❌ No se encontraron miniaturas de fotos para seleccionar con los selectores proporcionados.")

        # --- Paso 8: Hacer clic en el botón "Next" ---
        print("\n--- Intentando hacer clic en el botón 'Next' ---")
        next_button_clicked = False
        for by, value in NEXT_BUTTON_LOCATORS:
            if wait_and_click(driver, by, value, timeout=10, description=f"Botón 'Next' ({value})"):
                print("✅ Clic en el botón 'Next' exitoso.")
                next_button_clicked = True
                time.sleep(3) # Esperar a que cargue la siguiente pantalla
                break
        
        if not next_button_clicked:
            raise Exception("❌ No se pudo hacer clic en el botón 'Next'.")


        print("\n=== ¡Flujo de interacción con Instagram completado exitosamente! ===")
        time.sleep(5) # Mantener la app abierta un poco antes de cerrar

    except Exception as e:
        print(f"\n❌ Ocurrió un error en el flujo de automatización: {e}")
        if driver:
            driver.save_screenshot("error_instagram_automation.png")
            print("Captura de pantalla de error guardada como 'error_instagram_automation.png'.")
    finally:
        print("\n--- Cerrando la aplicación como una persona (pulsando Atrás) ---")
        try:
            # Presionar el botón Atrás varias veces para asegurar que la app se cierra por completo
            for _ in range(4): 
                driver.press_keycode(4) # KEYCODE_BACK es 4 en Android
                print("Presionada tecla Atrás.")
                time.sleep(1) 
        except Exception as e:
            print(f"❌ Error al presionar el botón Atrás al finalizar: {e}")
        
        print("Finalizando la sesión de Appium.")
        if driver:
            driver.quit() 

if __name__ == "__main__":
    test_instagram_interaction()

