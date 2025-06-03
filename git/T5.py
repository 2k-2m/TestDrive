from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import time
import csv
import random

def setup_driver():
    desired_caps = {
        "platformName": "Android",
        "deviceName": "R58M795NHZF",
        "appPackage": "com.instagram.android",
        "appActivity": "com.instagram.android.activity.MainTabActivity",
        "automationName": "UiAutomator2",
        "forceAppLaunch": True,
        "noReset": True,
        "newCommandTimeout": 300
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

def guardar_tiempo_en_txt_y_csv(segundos):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Guardar en .txt
    with open("tiempos_carga.txt", "a", encoding="utf-8") as txt_file:
        txt_file.write(f"{timestamp} - Tiempo de carga: {segundos:.2f} segundos\n")

    # Guardar en .csv
    with open("tiempos_carga.csv", "a", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow([timestamp, round(segundos, 2)])

    print("📝 Tiempo guardado en archivos 'tiempos_carga.txt' y 'tiempos_carga.csv'.")

def measure_feed_load_time(driver):
    print("\n⏱️ Starting timer to measure feed load time...")
    start_time = time.time()

    try:
        WebDriverWait(driver, 30).until(
            lambda d: d.find_element(AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().resourceId("com.instagram.android:id/refreshable_container")')
        )
        end_time = time.time()
        load_duration = end_time - start_time
        print(f"✅ Feed (For You page) loaded in {load_duration:.2f} seconds.")
        guardar_tiempo_en_txt_y_csv(load_duration)
        return load_duration
    except Exception as e:
        print(f"❌ Failed to detect feed container in time: {e}")
        return None

def is_logged_in(driver):
    print("Checking if already logged in by looking for Instagram logo...")
    try:
        logo = driver.find_element(AppiumBy.ID, "com.instagram.android:id/title_logo_chevron_container")
        if logo.is_displayed():
            print("✅ Instagram logo found. User appears to be logged in.")
            return True
        else:
            print("❌ Instagram logo not visible.")
            return False
    except NoSuchElementException:
        print("❌ Instagram logo not found. User is likely not logged in.")
        return False
    except Exception as e:
        print(f"An error occurred while checking login status: {e}")
        return False

def profile_button(driver):
    print("Navigating to profile by clicking avatar icon...")
    try:
        avatar_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((AppiumBy.ID, "com.instagram.android:id/tab_avatar"))
        )
        avatar_button.click()
        print("✅ Clicked on avatar icon to go to profile.")
        time.sleep(2)
    except Exception as e:
        print(f"❌ Failed to click avatar icon: {e}")  

def click_tab_icon(driver):
    print("Attempting to click icon...")
    try:
        icon = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().resourceId("com.instagram.android:id/tab_icon").instance(2)'
            ))
        )
        icon.click()
        print("✅ Successfully clicked the tab icon.")
        time.sleep(3)
    except Exception as e:
        print(f"❌ Failed to click tab icon: {e}")


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


def next_button_publi(driver, timeout=8):
    """
    Espera y hace clic en el botón 'Next' durante el proceso de publicación en Instagram.
    """
    print("🔍 Esperando el botón 'Next'")
    try:
        next_button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().resourceId("com.instagram.android:id/next_button_textview")'
            ))
        )
        next_button.click()
        print("✅ Click en el botón 'Next' exitoso.")
        time.sleep(2)
        return True
    except Exception as e:
        print(f"❌ Falló el clic en el botón 'Next': {e}")
        return False

def next_button_crea(driver, timeout=8):
    print("🔍 Esperando el botón 'Siguiente'")
    try:
        next_button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().resourceId("com.instagram.android:id/creation_next_button")'
            ))
        )
        next_button.click()
        print("✅ Click en el botón 'Siguiente' exitoso.")
        time.sleep(2)
        return True
    except Exception as e:
        print(f"❌ Falló el clic en el botón 'Siguiente': {e}")
        return False

def share_post_button(driver, timeout=8):
    print("🔍 Esperando el botón 'Compartir' (share_footer_button)...")
    try:
        share_button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().resourceId("com.instagram.android:id/share_footer_button")'
            ))
        )
        share_button.click()
        print("✅ Click en el botón 'Compartir' (share_footer_button) exitoso.")
        time.sleep(2)
        return True
    except Exception as e:
        print(f"❌ Falló el clic en el botón 'Compartir': {e}")
        return False


def test_instagram_login_or_skip():
    driver = None
    try:
        driver = setup_driver()
        if driver:
            print("\n--- Instagram Automation Started ---")
            print("Launching Instagram app...")
            
            # ⏱️ Medir tiempo de carga del feed
            measure_feed_load_time(driver)

            if is_logged_in(driver):
                print("Skipping login process as user is already logged in.")
                time.sleep(5)
                profile_button(driver)
                click_tab_icon(driver)
                random_photo(driver, PHOTO_THUMBNAIL_LOCATORS)
                next_button_publi(driver)
                next_button_crea(driver)

            else:
                print("User is not logged in. Proceeding with login flow.")
                
                username = "drivetest.2025.viva@gmail.com"
                password = "drivetestviv@2025_face"

                try:
                    username_field = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR,
                        'new UiSelector().className("android.widget.EditText").instance(0)')
                    username_field.send_keys(username)
                    print(f"✅ Entered username: {username}")
                    time.sleep(2)
                except Exception as e:
                    print(f"❌ Could not find username field: {e}")
                    driver.save_screenshot("error_username_field.png")
                    return

                try:
                    password_field = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR,
                        'new UiSelector().className("android.widget.EditText").instance(1)')
                    password_field.send_keys(password)
                    print("✅ Entered password.")
                    time.sleep(2)
                except Exception as e:
                    print(f"❌ Could not find password field: {e}")
                    driver.save_screenshot("error_password_field.png")
                    return

                try:
                    login_button = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR,
                        'new UiSelector().description("Iniciar sesión")')
                    login_button.click()
                    print("✅ Clicked on 'Iniciar sesión' button.")
                    time.sleep(10)
                except Exception as e:
                    print(f"❌ Could not click login button: {e}")
                    driver.save_screenshot("error_login_button.png")
                    return

                try:
                    time.sleep(5)
                    save_login_button = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR,
                        'new UiSelector().description("Guardar")')
                    save_login_button.click()
                    print("✅ Clicked on 'Guardar' button.")
                    time.sleep(5)
                except NoSuchElementException:
                    print("ℹ️ 'Guardar' button not found. Skipping.")
                except Exception as e:
                    print(f"Unexpected error with 'Guardar' button: {e}")

                print("✅ Instagram login completed successfully.")

            print("Instagram app will now be closed.")

    except Exception as e:
        print(f"❌ An error occurred during the test: {e}")
        if driver:
            driver.save_screenshot("error_general_test.png")
            print("Screenshot saved as 'error_general_test.png'.")
    finally:
        print("\n--- Automation Finished ---")
        if driver:
            driver.quit()

if __name__ == "__main__":
    test_instagram_login_or_skip()

