from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException
import time

def setup_driver():
    """
    Sets up the Appium WebDriver with desired capabilities for Instagram.
    """
    desired_caps = {
        "platformName": "Android",
        "deviceName": "R58M795NHZF",  # Replace with your actual device name
        "appPackage": "com.instagram.android",
        "appActivity": "com.instagram.android.activity.MainTabActivity",
        "automationName": "UiAutomator2",
        "forceAppLaunch": True,
        "noReset": True,
        "newCommandTimeout": 300
    }

    options = UiAutomator2Options().load_capabilities(desired_caps)
    driver = None
    try:
        print("Attempting to connect to Appium server...")
        driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
        print("✅ Successfully connected to Appium server.")
        return driver
    except Exception as e:
        print(f"❌ Failed to connect to Appium server or start session: {e}")
        return None

def measure_feed_load_time(driver):
    """
    Measures how long it takes for the Instagram feed (For You page) to load.
    """
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
        return load_duration
    except Exception as e:
        print(f"❌ Failed to detect feed container in time: {e}")
        return None

def is_logged_in(driver):
    """
    Checks if the user is already logged into Instagram by looking for the Instagram logo.
    """
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

def test_instagram_login_or_skip():
    driver = None
    try:
        driver = setup_driver()
        if driver:
            print("\n--- Instagram Automation Started ---")
            print("Launching Instagram app...")
            
            # 🕒 Medir tiempo de carga del feed
            feed_load_time = measure_feed_load_time(driver)

            if is_logged_in(driver):
                print("Skipping login process as user is already logged in.")
                time.sleep(5)
            else:
                print("User is not logged in. Proceeding with login flow.")
                
                username = "drivetest.2025.viva@gmail.com"
                password = "drivetestviv@2025_face"

                # Ingresar usuario
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

                # Ingresar contraseña
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

                # Botón "Iniciar sesión"
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

                # Botón "Guardar" (opcional)
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
