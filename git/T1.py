from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException # Import for checking element existence
import time

def setup_driver():
    """
    Sets up the Appium WebDriver with desired capabilities for Instagram.
    """
    desired_caps = {
        "platformName": "Android",
        "deviceName": "R58M795NHZF",  # <--- IMPORTANT: Use your actual device name from 'adb devices'
        "appPackage": "com.instagram.android",
        "appActivity": "com.instagram.android.activity.MainTabActivity",
        "automationName": "UiAutomator2",
        "forceAppLaunch": True,
        "noReset": True,# Keep this False for a clean start if not logged in.
                           # Set to True if you explicitly want to preserve session data across runs,
                           # but be aware it might skip login even when you want to test it.
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

def is_logged_in(driver):
    """
    Checks if the user is already logged into Instagram by looking for the Instagram logo.
    """
    print("Checking if already logged in by looking for Instagram logo...")
    try:
        # Using resourceId for the Instagram title logo
        instagram_logo = driver.find_element(AppiumBy.ID, "com.instagram.android:id/title_logo_chevron_container")
        
        if instagram_logo.is_displayed():
            print("✅ Instagram logo found. User appears to be logged in.")
            return True
        else:
            print("❌ Instagram logo not visible. User might not be logged in or UI loaded differently.")
            return False
    except NoSuchElementException:
        print("❌ Instagram logo not found. User is likely not logged in.")
        return False
    except Exception as e:
        print(f"An error occurred while checking login status with logo: {e}")
        return False

def test_instagram_login_or_skip():
    driver = None
    try:
        driver = setup_driver()
        if driver:
            print("\n--- Instagram Automation Started ---")
            print("Launching Instagram app...")
            time.sleep(10) # Give app some time to fully launch

            if is_logged_in(driver):
                print("Skipping login process as user is already logged in.")
                time.sleep(5) # Just wait a bit to observe the logged-in state
            else:
                print("User is not logged in. Proceeding with login flow.")
                
                # Define credentials
                username = "drivetest.2025.viva@gmail.com"
                password = "drivetestviv@2025_face"

                # Find and enter username
                try:
                    username_field = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().className("android.widget.EditText").instance(0)')
                    username_field.send_keys(username)
                    print(f"✅ Entered username: {username}")
                    time.sleep(2)
                except Exception as e:
                    print(f"❌ Could not find or interact with username field: {e}")
                    driver.save_screenshot("error_username_field.png")
                    return

                # Find and enter password
                try:
                    password_field = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().className("android.widget.EditText").instance(1)')
                    password_field.send_keys(password)
                    print("✅ Entered password.")
                    time.sleep(2)
                except Exception as e:
                    print(f"❌ Could not find or interact with password field: {e}")
                    driver.save_screenshot("error_password_field.png")
                    return

                # Click the login button
                try:
                    login_button = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().description("Iniciar sesión")')
                    login_button.click()
                    print("✅ Clicked on 'Iniciar sesión' button.")
                    time.sleep(10) # Wait for login to process and potential "Save Login Info" prompt
                except Exception as e:
                    print(f"❌ Could not find or click the login button: {e}")
                    driver.save_screenshot("error_login_button.png")
                    return

                # Handle "Save Login Info" prompt (optional)
                try:
                    time.sleep(5)
                    save_login_button = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().description("Guardar")')
                    save_login_button.click()
                    print("✅ Clicked on 'Guardar' (Save Login Info) button.")
                    time.sleep(5)
                except NoSuchElementException:
                    print("ℹ️ 'Guardar' (Save Login Info) button not found or already dismissed. Proceeding.")
                except Exception as e:
                    print(f"An unexpected error occurred while handling 'Guardar' button: {e}")

                print("✅ Instagram login test completed successfully.")
            
            print("Instagram app will remain open on your device.")

    except Exception as e:
        print(f"❌ An error occurred during the test: {e}")
        if driver:
            driver.save_screenshot("error_general_test.png")
            print("Screenshot saved as 'error_general_test.png'.")
    finally:
        print("\n--- Automation Finished ---")
        # driver.quit() is intentionally removed to keep the app open
        driver.quit()

if __name__ == "__main__":
    test_instagram_login_or_skip()