from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time

def wait_and_click(driver, by, value, timeout=15):
    try:
        element = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, value)))
        element.click()
        return True
    except:
        return False

def wait_for_presence(driver, by, value, timeout=15):
    try:
        return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))
    except:
        return None

def test_instagram_interaction():
    desired_caps = {
        "platformName": "Android",
        "deviceName": "emulator-5554",
        "appPackage": "com.instagram.android",
        "appActivity": "com.instagram.android.activity.MainTabActivity",
        "automationName": "UiAutomator2",
        "autoGrantPermissions": True,
        "noReset": False,  # IMPORTANTE para que aparezcan los popups
        "newCommandTimeout": 300
    }

    options = UiAutomator2Options().load_capabilities(desired_caps)
    driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
    wait = WebDriverWait(driver, 30)

    try:
        # --- LOGIN ---
        user_field = wait_for_presence(driver, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().className("android.widget.EditText").instance(0)')
        if user_field:
            user_field.clear()
            user_field.send_keys("drivetest.2025.viva@gmail.com")

            password_field = wait_for_presence(driver, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().className("android.widget.EditText").instance(1)', timeout=10)
            if password_field:
                password_field.clear()
                password_field.send_keys("drivetestviv@2025_face")

        # Clic en el botón de login
        wait_and_click(driver, AppiumBy.XPATH, '//android.view.View[@content-desc="Log in"]')
        time.sleep(5)  # Esperar por navegación

        # --- OPCIÓN: Log into another account ---
        log_into_another = wait_for_presence(driver, AppiumBy.XPATH, '//android.widget.TextView[@text="Log into another account"]', timeout=10)
        if log_into_another:
            print("❗ Detectado 'Log into another account'")
            log_into_another.click()
            time.sleep(5)

        # --- OPCIÓN: Save Your Login Info - Not Now ---

        # Intento 1: Texto visible tipo botón
        not_now_btn = wait_for_presence(driver, AppiumBy.XPATH, '//android.widget.Button[@text="Not now"]', timeout=5)
        if not_now_btn:
            not_now_btn.click()
            print("✅ Clic en 'Not now' (Button)")
        else:
            # Intento 2: Puede ser un TextView (frecuente en Instagram)
            not_now_text = wait_for_presence(driver, AppiumBy.XPATH, '//android.widget.TextView[@text="Not now"]', timeout=5)
            if not_now_text:
                not_now_text.click()
                print("✅ Clic en 'Not now' (TextView)")
            else:
                # Intento 3: Usar scroll y buscar en jerarquía con contains
                scrolled_not_now = wait_for_presence(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                    'new UiSelector().textContains("Not now")', timeout=5)
                if scrolled_not_now:
                    scrolled_not_now.click()
                    print("✅ Clic en 'Not now' (con scroll/textContains)")
                else:
                    print("⚠️ No se encontró el botón 'Not now'")
        # --- PERMISOS ---
        wait_and_click(driver, AppiumBy.ID, "com.android.permissioncontroller:id/permission_deny_button", timeout=5)
        wait_and_click(driver, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Don’t allow")', timeout=5)

        # --- VALIDACIÓN DEL LOGO ---
        if wait_for_presence(driver, AppiumBy.ACCESSIBILITY_ID, "Instagram logo", timeout=20):
            print("✅ Login exitoso.")
        else:
            raise Exception("❌ No se detectó el logo de Instagram.")

        time.sleep(5)
        """
        # --- SUBIR IMAGEN (opcional, puede fallar según estado de sesión) ---
        print("📤 Intentando subir una imagen...")

        wait_and_click(driver, AppiumBy.ACCESSIBILITY_ID, "What’s on your mind?")
        wait_and_click(driver, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Photo")')

        image = wait_for_presence(driver, AppiumBy.CLASS_NAME, "android.widget.ImageView", timeout=10)
        if image:
            image.click()
        else:
            print("⚠️ No se encontró una imagen para subir.")

        wait_and_click(driver, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Post")')
        print("✅ Imagen publicada.")
        time.sleep(10)

        # --- REPRODUCIR VIDEO (opcional) ---
        print("▶️ Buscando un video para reproducir...")
        video_found = False
        for _ in range(3):
            videos = driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.ImageView")
            for v in videos:
                try:
                    desc = v.get_attribute("content-desc")
                    if desc and "video" in desc.lower():
                        v.click()
                        print("🎥 Video encontrado y reproducido.")
                        video_found = True
                        time.sleep(10)
                        driver.back()
                        break
                except:
                    continue
            if video_found:
                break
            driver.swipe(500, 1500, 500, 300, 800)
            time.sleep(3)

        if not video_found:
            print("⚠️ No se encontró un video para reproducir.")
        """
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        driver.quit()


if __name__ == "__main__":
    test_instagram_interaction()
