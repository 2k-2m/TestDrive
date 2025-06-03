from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time

def wait_and_click(driver, by, value, timeout=10, description="Elemento"):
    """
    Espera hasta que un elemento sea clicable y le da click.
    Imprime mensajes para depuración.
    """
    try:
        print(f"Intentando hacer clic en '{description}' (By: {by}, Value: '{value}')...")
        element = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, value)))
        # Añadimos un pequeño sleep aquí por si el elemento necesita estabilizarse
        time.sleep(0.5)
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

# --- Selectores para Pop-ups (Denegar/No Ahora/Omitir) ---
POPUP_DENY_LOCATORS = [
    # **MANTENEMOS SOLO EL QUE FUNCIONÓ Y ALGUNOS RESPALDOS CLAVE**
    (AppiumBy.XPATH, "//*[contains(@text, 'Not now') or contains(@text, 'Ahora no')]"), # Este funcionó
    (AppiumBy.ID, "android:id/button2"), # Botón "No, gracias" del sistema (para guardar credenciales)
    (AppiumBy.ID, "com.android.permissioncontroller:id/permission_deny_button"), # Botón "Denegar" permisos
    (AppiumBy.XPATH, "//*[contains(@text, 'Omitir') or contains(@text, 'Skip')]"), # Omitir historias, etc.
]

# --- SELECTORES OPTIMIZADOS PARA EL BOTÓN "CONTINUE" ---
CONTINUE_BUTTON_LOCATORS = [
    # **MANTENEMOS SOLO EL QUE FUNCIONÓ COMO PRINCIPAL**
    (AppiumBy.XPATH, '//android.widget.Button[@content-desc="Continue"]/android.view.ViewGroup'), 
    # Podemos dejar uno o dos respaldos MUY genéricos por si el principal falla en el futuro
    (AppiumBy.ACCESSIBILITY_ID, "Continue"),
    (AppiumBy.XPATH, '//*[contains(@text, "Continue") or contains(@content-desc, "Continue")]'),
]

# --- SELECTORES PARA EL AVATAR ---
AVATAR_LOCATORS = [
    (AppiumBy.ID, "com.instagram.android:id/tab_avatar"),
    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().resourceId("com.instagram.android:id/tab_avatar")'),
    (AppiumBy.XPATH, '//android.widget.ImageView[@resource-id="com.instagram.android:id/tab_avatar"]'),
]

# --- SELECTORES PARA VALIDAR LA PÁGINA PRINCIPAL (¡NECESITAN AJUSTE CON INFO DEL INSPECTOR!) ---
MAIN_PAGE_VALIDATION_LOCATORS = [
    # Placeholder: Reemplaza con los selectores exactos del logo de Instagram o del botón "Inicio"
    # que obtengas del Appium Inspector.
    # Ejemplo 1 (si el logo tiene un content-desc):
    # (AppiumBy.ACCESSIBILITY_ID, "Instagram logo"), 
    # Ejemplo 2 (si el botón de inicio tiene un content-desc o texto):
    # (AppiumBy.ACCESSIBILITY_ID, "Inicio"), 
    # (AppiumBy.XPATH, '//android.widget.FrameLayout[@content-desc="Inicio"]'), # Podría ser un FrameLayout
    # (AppiumBy.XPATH, '//*[contains(@content-desc, "Inicio") or contains(@text, "Inicio")]'),

    # **ACÁ ABAJO DEBES AGREGAR EL/LOS SELECTOR/ES REALES QUE ENCUENTRES CON APPIUM INSPECTOR**
    # Por ejemplo:
    (AppiumBy.ID, "com.instagram.android:id/action_bar_title"), # Título en la barra superior que a veces es "Instagram"
    (AppiumBy.XPATH, '//android.widget.ImageView[@content-desc="Instagram"]'), # El logo de la app podría tener este content-desc
    (AppiumBy.XPATH, '//android.widget.FrameLayout[@content-desc="Inicio" or @content-desc="Home"]'), # El botón de inicio en la barra inferior
    (AppiumBy.XPATH, '//android.widget.FrameLayout[@content-desc="Perfil" or @content-desc="Profile"]'), # Otro botón de la barra inferior que indica que estás en la app
    (AppiumBy.XPATH, '//android.widget.ImageView[@content-desc="Cámara"]'), # El icono de la cámara en la parte superior izquierda
    # Puedes añadir más según lo que veas en el Inspector y sea estable.
]


def handle_instagram_popups(driver):
    """
    Intenta cerrar cualquier pop-up que pueda aparecer después del login.
    """
    print("\n--- Manejando posibles Pop-ups de Instagram ---")
    popups_handled_count = 0
    # Aumentamos el número de iteraciones por si hay varios popups en fila
    for i in range(7): 
        popup_closed_in_iteration = False
        for by, value in POPUP_DENY_LOCATORS:
            # Reducimos el timeout para los popups a 2 segundos si no son el primero que ya sabemos que funciona
            current_popup_timeout = 5 if value == POPUP_DENY_LOCATORS[0][1] else 2 
            if wait_and_click(driver, by, value, timeout=current_popup_timeout, description=f"Botón de Pop-up IG ({value})"):
                popup_closed_in_iteration = True
                popups_handled_count += 1
                time.sleep(1) # Pequeña pausa después de cerrar un popup
                break
        if not popup_closed_in_iteration:
            break
    if popups_handled_count > 0:
        print(f"✅ Se manejaron {popups_handled_count} pop-ups de Instagram.")
    else:
        print("ℹ️ No se detectaron pop-ups conocidos de Instagram para manejar.")
    time.sleep(2)

def test_instagram_interaction():
    desired_caps = {
        "platformName": "Android",
        "deviceName": "emulator-5554",  # <--- CAMBIA ESTO
        "appPackage": "com.instagram.android",
        "appActivity": "com.instagram.android.activity.MainTabActivity",
        "automationName": "UiAutomator2",
        "autoGrantPermissions": True,
        "noReset": False,
        "newCommandTimeout": 300,
        "unlockType": "pin",
        "unlockKey": "1234"  # <--- CAMBIA ESTO
    }

    options = UiAutomator2Options().load_capabilities(desired_caps)
    driver = None
    try:
        driver = webdriver.Remote("http://127.0.0.1:4723", options=options)

        print("Iniciando prueba de Instagram...")

        INSTAGRAM_USERNAME = "drivetest.2025.viva@gmail.com"
        INSTAGRAM_PASSWORD = "drivetestviv@2025_face"

        # **Paso 1: Manejar la pantalla "Continue" si aparece**
        continue_clicked = False
        print("Intentando hacer clic en el botón 'Continue' (si aparece)...")
        for by, value in CONTINUE_BUTTON_LOCATORS:
            if wait_and_click(driver, by, value, timeout=7, description=f"Botón 'Continue' ({value})"):
                print("✅ Clic en 'Continue' exitoso.")
                continue_clicked = True
                time.sleep(5) 
                break 
        
        if continue_clicked:
            print("Pantalla 'Continue' manejada. Procediendo con el flujo.")
        else:
            print("Pantalla 'Continue' no detectada o no se pudo hacer clic. Procediendo con login explícito.")

        # --- LOGIN EXPLÍCITO (si es necesario) ---
        if not continue_clicked:
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
        else:
            print("Login explícito omitido ya que la pantalla 'Continue' fue manejada.")

        # --- Manejo de pop-ups POST-LOGIN (incluye el "Log into another account" si aparece) ---
        # El "Log into another account" no se encontró, lo quitamos de esta función y lo ponemos en handle_instagram_popups
        # Si Appium Inspector te muestra que ese pop-up aún es posible, podemos reevaluar su lugar.
        # Por ahora, handle_instagram_popups lo manejará si aparece con "Not now" o "Ahora no"
        
        handle_instagram_popups(driver)

        # --- VALIDACIÓN DE LA PÁGINA PRINCIPAL (¡AJUSTAR SELECTORES!) ---
        print("\n--- Validando que la página principal de Instagram sea visible ---")
        main_page_visible = False
        for by, value in MAIN_PAGE_VALIDATION_LOCATORS:
            if wait_for_presence(driver, by, value, timeout=10, description=f"Elemento de página principal ({value})"):
                print(f"✅ Elemento '{value}' encontrado. Página principal visible.")
                main_page_visible = True
                break
        
        if not main_page_visible:
            raise Exception("❌ No se detectó ningún elemento clave de la página principal. Posiblemente hay un pop-up o la pantalla no cargó.")

        print("Esperando unos segundos en la página principal...")
        time.sleep(3) 

        # --- HACER TAP EN EL AVATAR ---
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

        # --- CERRAR LA APLICACIÓN COMO UNA PERSONA ---
        print("\n--- Cerrando la aplicación como una persona (pulsando Atrás) ---")
        for _ in range(4): # Intentar 4 veces el botón de atrás para asegurar la salida
            driver.press_keycode(4) # KEYCODE_BACK es 4
            print("Presionada tecla Atrás.")
            time.sleep(1) 

    except Exception as e:
        print(f"❌ Ocurrió un error: {e}")
        if driver:
            driver.save_screenshot("error_instagram_automation.png")
            print("Captura de pantalla de error guardada como 'error_instagram_automation.png'.")
    finally:
        print("Finalizando la sesión de Appium.")
        if driver:
            driver.quit() 

if __name__ == "__main__":
    test_instagram_interaction()