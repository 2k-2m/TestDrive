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
    # Botón "Not now" o "Ahora no" (texto)
    (AppiumBy.XPATH, "//*[contains(@text, 'Not now') or contains(@text, 'Ahora no')]"),
    (AppiumBy.XPATH, "//android.widget.Button[contains(@text, 'Not now')]"),
    (AppiumBy.ACCESSIBILITY_ID, "Not now"),
    # Botón "Omitir" o "Skip"
    (AppiumBy.XPATH, "//*[contains(@text, 'Omitir') or contains(@text, 'Skip')]"),
    # Botón "Denegar" o "Deny" (típico para permisos del sistema)
    (AppiumBy.ID, "com.android.permissioncontroller:id/permission_deny_button"),
    (AppiumBy.XPATH, "//*[contains(@text, 'Denegar') or contains(@text, 'Deny')]"),
    # Botón "No, gracias" o "No Thanks" (típico para guardar credenciales)
    (AppiumBy.ID, "android:id/button2"),
    (AppiumBy.XPATH, "//*[contains(@text, 'No, gracias') or contains(@text, 'No Thanks')]")
]

# --- SELECTORES MEJORADOS Y EXTENDIDOS PARA EL BOTÓN "CONTINUE" ---
CONTINUE_BUTTON_LOCATORS = [
    # 1. El XPath específico que proporcionaste con ViewGroup (muy potente si es exacto)
    (AppiumBy.XPATH, '//android.widget.Button[@content-desc="Continue"]/android.view.ViewGroup'),
    
    # 2. Tu UiSelector con className y instance (siempre que la instancia sea estable)
    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().className("android.view.ViewGroup").instance(12)'),
    
    # 3. El XPath directo del botón con content-desc (muy común)
    (AppiumBy.XPATH, '//android.widget.Button[@content-desc="Continue"]'),
    
    # 4. El UiSelector directo del texto "Continue" (si es un TextView y no un Button)
    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Continue")'),
    
    # 5. El XPath para View con content-desc (si no es un Button pero es una View general)
    (AppiumBy.XPATH, '//android.view.View[@content-desc="Continue"]'),

    # 6. El XPath del botón por texto (lo más común, aunque dijiste que ahora no salía "Continue as")
    (AppiumBy.XPATH, '//android.widget.Button[@text="Continue"]'),
    
    # 7. Accessibility ID (también común)
    (AppiumBy.ACCESSIBILITY_ID, "Continue"),
    
    # 8. XPaths genéricos con contains (último recurso por si hay espacios o caracteres especiales)
    (AppiumBy.XPATH, '//*[contains(@text, "Continue") and @clickable="true"]'),
    (AppiumBy.XPATH, '//*[contains(@content-desc, "Continue") and @clickable="true"]'),
]


def handle_instagram_popups(driver):
    """
    Intenta cerrar cualquier pop-up que pueda aparecer después del login.
    """
    print("\n--- Manejando posibles Pop-ups de Instagram ---")
    popups_handled_count = 0
    for i in range(5):
        popup_closed_in_iteration = False
        for by, value in POPUP_DENY_LOCATORS:
            if wait_and_click(driver, by, value, timeout=3, description=f"Botón de Pop-up IG ({value})"):
                popup_closed_in_iteration = True
                popups_handled_count += 1
                time.sleep(1)
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
        # No buscamos el nombre de usuario, solo intentamos darle clic al botón "Continue"
        continue_clicked = False
        print("Intentando hacer clic en el botón 'Continue' (si aparece)...")
        for by, value in CONTINUE_BUTTON_LOCATORS:
            if wait_and_click(driver, by, value, timeout=7, description=f"Botón 'Continue' ({value})"):
                print("✅ Clic en 'Continue' exitoso.")
                continue_clicked = True
                time.sleep(5) # Dar tiempo a la app para cargar después de continuar
                break # Salir del bucle una vez que se haga clic
        
        if continue_clicked:
            print("Pantalla 'Continue' manejada. Procediendo con el flujo.")
        else:
            print("Pantalla 'Continue' no detectada o no se pudo hacer clic. Procediendo con login explícito.")


        # --- LOGIN EXPLÍCITO (si es necesario) ---
        # Solo intentar el login explícito si el botón "Continue" no fue clicado.
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

            # Clic en el botón de login
            if not wait_and_click(driver, AppiumBy.XPATH, '//android.view.View[@content-desc="Log in"]', description="Botón de Log in"):
                 raise Exception("❌ No se pudo hacer clic en el botón de Log in.")
            print("✅ Clic en botón de Log in exitoso.")
            time.sleep(5)
        else:
            print("Login explícito omitido ya que la pantalla 'Continue' fue manejada.")


        # --- Manejo de pop-ups POST-LOGIN ---
        # Primero, el "Log into another account" si aparece.
        if wait_and_click(driver, AppiumBy.XPATH, '//android.widget.TextView[@text="Log into another account"]', timeout=5, description="Opción 'Log into another account'"):
            print("✅ Clic en 'Log into another account' exitoso.")
            time.sleep(3)

        handle_instagram_popups(driver)

        # --- VALIDACIÓN DEL LOGO ---
        if wait_for_presence(driver, AppiumBy.ACCESSIBILITY_ID, "Instagram logo", timeout=20, description="Logo de Instagram") or \
           wait_for_presence(driver, AppiumBy.ACCESSIBILITY_ID, "Inicio", timeout=20, description="Botón de Inicio"):
            print("✅ Login exitoso y pop-ups manejados.")
        else:
            raise Exception("❌ No se detectó el logo de Instagram o el botón de Inicio. Login podría haber fallado o hay pop-ups inesperados.")

        print("El script ahora podría continuar con otras interacciones en Instagram.")
        time.sleep(5)

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