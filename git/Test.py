from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def setup_driver():
    """
    Sets up the Appium WebDriver with desired capabilities for Instagram.
    """
    desired_caps = {
        "platformName": "Android",
        "deviceName": "R58M795NHZF",  # <--- IMPORTANT: Use your actual device name from 'adb devices'
        "appPackage": "com.instagram.android",
        "appActivity": "com.instagram.android.activity.MainTabActivity", # <--- PUTTING appActivity BACK IN
        "automationName": "UiAutomator2",
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

def is_on_homepage(driver):
    """
    Checks if the current screen is the Instagram homepage by looking for the Instagram logo.
    This is for direct measurement.
    """
    print("Attempting to detect Instagram homepage...")
    try:
        # We'll try to find the logo with a short wait to see if it's immediately present
        WebDriverWait(driver, 5).until( # Shorter wait here
            EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/title_logo_chevron_container"))
        )
        print("✅ Instagram logo found. App appears to be on homepage.")
        return True
    except TimeoutException:
        print("❌ Instagram logo not immediately found. Not on homepage or app is loading login.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while checking for homepage: {e}")
        return False

def wait_for_homepage_content_load(driver, timeout=30):
    """
    Waits until the 'refreshable_container' (main feed content area) is present.
    """
    print(f"Waiting for 'refreshable_container' to load (max {timeout} seconds)...")
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/refreshable_container"))
        )
        print("✅ 'refreshable_container' found. Homepage content loaded.")
        return True
    except TimeoutException:
        print(f"❌ 'refreshable_container' not found within {timeout} seconds. Homepage content did not load.")
        return False
    except Exception as e:
        print(f"An error occurred while waiting for homepage content: {e}")
        return False


def test_instagram_app_load_time():
    driver = None
    try:
        driver = setup_driver()
        if driver:
            print("\n--- Instagram Automation Started ---")
            
            # --- START: Time Measurement ---
            # Start timer right after Appium session is established, before app launch/interaction
            start_time = time.time()
            print(f"⏱️ Starting timer for app launch and 'For You Page' load at {time.ctime(start_time)}.")
            # --- END: Time Measurement ---

            print("Attempting to launch/bring Instagram to foreground...")
            # Give a small initial buffer for the app to come to foreground
            time.sleep(3) 

            # Check if we are already on the homepage (logged in)
            if is_on_homepage(driver):
                print("App launched directly to homepage. Waiting for content.")
            else:
                # If not on homepage, we assume it's on a login or welcome screen
                print("App not immediately on homepage. Attempting login flow.")
                
                username = "drivetest.2025.viva@gmail.com"
                password = "drivetestviv@2025_face"

                # Find and enter username
                try:
                    username_field = WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().className("android.widget.EditText").instance(0)'))
                    )
                    username_field.send_keys(username)
                    print(f"✅ Entered username: {username}")
                    time.sleep(2)
                except Exception as e:
                    print(f"❌ Could not find or interact with username field: {e}. App might be stuck on initial screen or no login form present.")
                    # driver.save_screenshot("error_username_field.png")
                    return

                # Find and enter password
                try:
                    password_field = WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().className("android.widget.EditText").instance(1)'))
                    )
                    password_field.send_keys(password)
                    print("✅ Entered password.")
                    time.sleep(2)
                except Exception as e:
                    print(f"❌ Could not find or interact with password field: {e}.")
                    # driver.save_screenshot("error_password_field.png")
                    return

                # Click the login button
                try:
                    login_button = WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().description("Iniciar sesión")'))
                    )
                    login_button.click()
                    print("✅ Clicked on 'Iniciar sesión' button.")
                    time.sleep(5)
                except Exception as e:
                    print(f"❌ Could not find or click the login button: {e}")
                    # driver.save_screenshot("error_login_button.png")
                    return

                # Handle "Save Login Info" prompt (optional)
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().description("Guardar")'))
                    ).click()
                    print("✅ Clicked on 'Guardar' (Save Login Info) button.")
                    time.sleep(5)
                except TimeoutException:
                    print("ℹ️ 'Guardar' (Save Login Info) button not found within timeout or already dismissed. Proceeding.")
                except Exception as e:
                    print(f"An unexpected error occurred while handling 'Guardar' button: {e}")

            # --- Critical: Wait for the homepage content AFTER all login/detection logic ---
            if not wait_for_homepage_content_load(driver):
                raise Exception("Homepage content did not load after app launch or login.")

            # --- END: Time Measurement ---
            end_time = time.time()
            elapsed_time = end_time - start_time
            print(f"\n✨ **Total time for 'For You Page' to load: {elapsed_time:.2f} seconds** ✨")
            # --- END: Time Measurement ---
            
            print("Instagram app will remain open on your device.")

    except Exception as e:
        print(f"❌ An error occurred during the test: {e}")
        if driver:
            # driver.save_screenshot("error_general_test.png")
            print("Screenshot saving temporarily disabled.")
    finally:
        print("\n--- Automation Finished ---")

if __name__ == "__main__":
    test_instagram_app_load_time()