from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import random 

# --- Funciones de Utilidad (SIN CAMBIOS, se mantienen las que ya tienes) ---
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

# --- Selectores de Elementos de la UI (SIN CAMBIOS) ---
POPUP_DENY_LOCATORS = [
    (AppiumBy.XPATH, "//*[contains(@text, 'Not now') or contains(@text, 'Ahora no')]"), 
    (AppiumBy.ID, "android:id/button2"), 
    (AppiumBy.ID, "com.android.permissioncontroller:id/permission_deny_button"), 
    # Añadir selector para "Instagram isn't responding" si lo encuentras.
    # Ej: (AppiumBy.XPATH, "//*[contains(@text, 'Wait') or contains(@text, 'Esperar')]"),
    # Ej: (AppiumBy.ID, "android:id/button1"), # Común para "Wait"
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
    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().resourceId("com.instagram.android:id/tab_icon").instance(2)'), 
    (AppiumBy.XPATH, '(//android.widget.ImageView[@resource-id="com.instagram.android:id/tab_icon"])[3]'), 
]

MAIN_PAGE_VALIDATION_LOCATORS = [
    (AppiumBy.XPATH, '//android.widget.FrameLayout[@content-desc="Inicio" or @content-desc="Home"]'), 
]

PHOTO_THUMBNAIL_LOCATORS = [
    (AppiumBy.XPATH, '//android.widget.GridView[@resource-id="com.instagram.android:id/media_picker_grid_view"]//android.widget.Button'),
    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().resourceId("com.instagram.android:id/media_picker_grid_view").childSelector(new UiSelector().className("android.widget.Button"))'),
    (AppiumBy.CLASS_NAME, "android.widget.Button"),
]

NEXT_BUTTON_LOCATORS = [
    (AppiumBy.ID, "com.instagram.android:id/next_button_textview"),
    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().resourceId("com.instagram.android:id/next_button_textview")'),
    (AppiumBy.XPATH, '//android.widget.Button[@content-desc="Next"]'),
]

# --- Función para Manejar Pop-ups (SIN CAMBIOS, usa la versión optimizada) ---
def handle_instagram_popups(driver):
    """
    Intenta cerrar cualquier pop-up que pueda aparecer.
    Optimizada para ser más eficiente al reintentar selectores.
    """
    print("\n--- Manejando posibles Pop-ups de Instagram ---")
    popups_handled_count = 0
    
    for i in range(5): 
        popup_found_and_clicked_in_this_round = False
        for by, value in POPUP_DENY_LOCATORS:
            current_timeout = 5 if (by == AppiumBy.XPATH and "Not now" in value) else 3 

            if wait_and_click(driver, by, value, timeout=current_timeout, description=f"Botón de Pop-up IG ({value})"):
                popup_found_and_clicked_in_this_round = True
                popups_handled_count += 1
                time.sleep(2) 
                break 
        
        if not popup_found_and_clicked_in_this_round:
            break

    if popups_handled_count > 0:
        print(f"✅ Se manejaron {popups_handled_count} pop-ups de Instagram.")
    else:
        print("ℹ️ No se detectaron pop-ups conocidos de Instagram para manejar.")
    time.sleep(1) 

# --- Nueva función para el flujo de una sola interacción ---
def run_instagram_flow(driver, is_first_iteration=False):
    """
    Contiene el flujo principal de interacción con Instagram.
    Ajusta el comportamiento de login basado en si es la primera iteración.
    """
    INSTAGRAM_USERNAME = "drivetest.2025.viva@gmail.com"
    INSTAGRAM_PASSWORD = "drivetestviv@2025_face"

    print(f"\n--- Iniciando flujo de Instagram (Primera iteración: {is_first_iteration}) ---")

    # --- Paso 1: Manejar la pantalla "Continue" o realizar Login completo ---
    if is_first_iteration:
        print("FORZANDO LOGIN COMPLETO para la primera iteración.")
        # En la primera iteración, siempre vamos a asumir que la pantalla de login aparecerá.
        # Si por alguna razón aparece "Continue" y la ignoramos, Appium puede quedarse esperando el login.
        # Es mejor esperar directamente los campos de usuario/contraseña.
        user_field = wait_for_presence(driver, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().className("android.widget.EditText").instance(0)', timeout=15, description="Campo de usuario")
        if user_field:
            user_field.clear()
            user_field.send_keys(INSTAGRAM_USERNAME)
            print(f"✅ Usuario '{INSTAGRAM_USERNAME}' ingresado.")
        else:
            raise Exception("❌ No se encontró el campo de usuario para login completo en la primera iteración.")

        password_field = wait_for_presence(driver, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().className("android.widget.EditText").instance(1)', timeout=10, description="Campo de contraseña")
        if password_field:
            password_field.clear()
            password_field.send_keys(INSTAGRAM_PASSWORD)
            print("✅ Contraseña ingresada.")
        else:
            raise Exception("❌ No se encontró el campo de contraseña.")

        if not wait_and_click(driver, AppiumBy.XPATH, '//android.view.View[@content-desc="Log in"]', description="Botón de Log in"):
             raise Exception("❌ No se pudo hacer clic en el botón de Log in.")
        print("✅ Clic en botón de Log in exitoso (Login completo).")
        time.sleep(7) # Más tiempo después de un login completo

    else: # No es la primera iteración, intentar "Continue" primero
        continue_clicked = False
        print("Intentando hacer clic en el botón 'Continue' (si aparece) para iteraciones subsiguientes...")
        for by, value in CONTINUE_BUTTON_LOCATORS:
            if wait_and_click(driver, by, value, timeout=7, description=f"Botón 'Continue' ({value})"):
                print("✅ Clic en 'Continue' exitoso.")
                continue_clicked = True
                time.sleep(5) 
                break 
        
        if continue_clicked:
            print("Pantalla 'Continue' manejada. Procediendo con el flujo.")
        else:
            print("Pantalla 'Continue' no detectada o no se pudo hacer clic. Procediendo con login explícito (si fuera necesario).")
            # Si no apareció "Continue", asumimos que la app no está logueada y hacemos el login completo.
            user_field = wait_for_presence(driver, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().className("android.widget.EditText").instance(0)', description="Campo de usuario")
            if user_field:
                user_field.clear()
                user_field.send_keys(INSTAGRAM_USERNAME)
                print(f"✅ Usuario '{INSTAGRAM_USERNAME}' ingresado.")
            else:
                raise Exception("❌ No se encontró el campo de usuario para login explícito.")

            password_field = wait_for_presence(driver, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().className("android.widget.EditText").instance(1)', timeout=10, description="Campo de contraseña")
            if password_field:
                password_field.clear()
                password_field.send_keys(INSTAGRAM_PASSWORD)
                print("✅ Contraseña ingresada.")
            else:
                raise Exception("❌ No se encontró el campo de contraseña.")

            if not wait_and_click(driver, AppiumBy.XPATH, '//android.view.View[@content-desc="Log in"]', description="Botón de Log in"):
                 raise Exception("❌ No se pudo hacer clic en el botón de Log in.")
            print("✅ Clic en botón de Log in exitoso.")
            time.sleep(5)


    # --- Paso 2: Manejo de pop-ups post-login ---
    handle_instagram_popups(driver)

    # --- Paso 3: Validar que la página principal de Instagram sea visible ---
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

    # --- Paso 4: Hacer clic en el avatar (para ir al perfil) ---
    print("\n--- Intentando hacer clic en el avatar (perfil) ---")
    avatar_clicked = False
    for by, value in AVATAR_LOCATORS:
        if wait_and_click(driver, by, value, timeout=10, description=f"Avatar (Perfil) ({value})"):
            print("✅ Clic en el avatar (perfil) exitoso.")
            avatar_clicked = True
            time.sleep(5) 
            break
    
    if not avatar_clicked:
        raise Exception("❌ No se pudo hacer clic en el avatar (botón de perfil).")

    print("Ahora estás en la página de perfil. Esperando unos segundos...")
    time.sleep(3)

    # --- Paso 5: Clic en el icono de publicaciones ---
    print("\n--- Intentando hacer clic en el icono de publicaciones (tercer tab_icon) ---")
    post_tab_clicked = False
    for by, value in POST_TAB_ICON_LOCATORS:
        if wait_and_click(driver, by, value, timeout=10, description=f"Icono de Publicaciones ({value})"):
            print("✅ Clic en el icono de publicaciones exitoso.")
            post_tab_clicked = True
            time.sleep(3) 
            break
    
    if not post_tab_clicked:
        print("ℹ️ No se pudo hacer clic en el icono de publicaciones, asumiendo que ya está en la vista correcta o no es necesario.")

    # --- Paso 6: Seleccionar una imagen aleatoriamente de las miniaturas ---
    print("\n--- Intentando seleccionar una miniatura de foto aleatoriamente ---")
    photo_elements = []
    for by, value in PHOTO_THUMBNAIL_LOCATORS:
        photo_elements = find_elements_safely(driver, by, value, timeout=10, description="Miniaturas de fotos")
        if photo_elements:
            break 
    
    if photo_elements:
        random_photo = random.choice(photo_elements)
        photo_description = random_photo.get_attribute('content-desc') or random_photo.text or f"Elemento (Clase: {random_photo.tag_name})"
        print(f"✅ Seleccionando miniatura de foto aleatoria: '{photo_description}'")
        random_photo.click()
        print("✅ Clic en miniatura de foto exitoso.")
        time.sleep(5) 
    else:
        raise Exception("❌ No se encontraron miniaturas de fotos para seleccionar con los selectores proporcionados.")

    # --- Paso 7: Hacer clic en el botón "Next" ---
    print("\n--- Intentando hacer clic en el botón 'Next' ---")
    next_button_clicked = False
    for by, value in NEXT_BUTTON_LOCATORS:
        if wait_and_click(driver, by, value, timeout=10, description=f"Botón 'Next' ({value})"):
            print("✅ Clic en el botón 'Next' exitoso.")
            next_button_clicked = True
            time.sleep(3) 
            break
    
    if not next_button_clicked:
        raise Exception("❌ No se pudo hacer clic en el botón 'Next'.")

    print("\n=== ¡Flujo de interacción con Instagram completado exitosamente! ===")
    time.sleep(3) # Pausa antes de la siguiente iteración o cierre


# --- Función Principal que maneja las iteraciones ---
def test_instagram_automation_cycle(num_cycles=10):
    for i in range(num_cycles):
        print(f"\n====================== INICIANDO CICLO {i + 1} DE {num_cycles} ======================")
        driver = None
        try:
            # Configuración de capacidades Appium
            desired_caps = {
                "platformName": "Android",
                "deviceName": "emulator-5554",  # <--- AJUSTA ESTO
                "appPackage": "com.instagram.android",
                "appActivity": "com.instagram.android.activity.MainTabActivity",
                "automationName": "UiAutomator2",
                "autoGrantPermissions": True,
                "newCommandTimeout": 300,
            }

            if i == 0:
                # Primera iteración: fuerza un reset completo para asegurar la pantalla de login
                desired_caps["noReset"] = False
                print(f"Capacidad 'noReset' establecida a {desired_caps['noReset']} para la primera iteración.")
            else:
                # Iteraciones siguientes: intenta reutilizar la sesión si es posible
                desired_caps["noReset"] = True
                print(f"Capacidad 'noReset' establecida a {desired_caps['noReset']} para las iteraciones subsiguientes.")
            
            options = UiAutomator2Options().load_capabilities(desired_caps)
            driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
            
            run_instagram_flow(driver, is_first_iteration=(i == 0))

        except Exception as e:
            print(f"\n❌ Ocurrió un error en el CICLO {i + 1}: {e}")
            if driver:
                driver.save_screenshot(f"error_instagram_automation_cycle_{i+1}.png")
                print(f"Captura de pantalla de error guardada como 'error_instagram_automation_cycle_{i+1}.png'.")
        finally:
            print(f"\n--- Finalizando sesión para el CICLO {i + 1} ---")
            if driver:
                try:
                    # Cerrar la aplicación suavemente con el botón atrás antes de quit
                    for _ in range(4): 
                        driver.press_keycode(4) 
                        time.sleep(1) 
                except Exception as e:
                    print(f"❌ Error al presionar el botón Atrás al finalizar el ciclo {i+1}: {e}")
                driver.quit()
            print(f"====================== CICLO {i + 1} FINALIZADO ======================\n")
            time.sleep(2) # Pequeña pausa entre ciclos

if __name__ == "__main__":
    test_instagram_automation_cycle(num_cycles=2) # Ejecutará el flujo 2 veces