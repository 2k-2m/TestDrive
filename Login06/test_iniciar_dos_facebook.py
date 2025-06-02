from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time

def test_login_facebook():
    desired_caps = {
        "platformName": "Android",
        "deviceName": "emulator-5554",  # usa el nombre del emulador en ejecución
        "appPackage": "com.facebook.katana",
        "appActivity": "com.facebook.katana.LoginActivity",
        "automationName": "UiAutomator2"
    }

    options = UiAutomator2Options().load_capabilities(desired_caps)
    driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
    wait = WebDriverWait(driver, 30)

    try:
        # Ingresar usuario
        user_field = wait.until(EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().className("android.widget.EditText").instance(0)')))
        user_field.clear()
        user_field.send_keys("drivetestviva2025@gmail.com")

        # Ingresar contraseña
        password_field = wait.until(EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().className("android.widget.EditText").instance(1)')))
        password_field.clear()
        password_field.send_keys("drivetestviv@2025_face")

        # Clic en login
        login_button = wait.until(EC.element_to_be_clickable((
            AppiumBy.XPATH, '//android.view.View[@content-desc="Log in"]'
        )))
        login_button.click()

        # Verificar y cerrar el mensaje de notificación si aparece
        try:
            deny_button = WebDriverWait(driver, 10).until(EC.presence_of_element_located((AppiumBy.ID, "com.android.permissioncontroller:id/permission_deny_button")))
            if deny_button.is_displayed():
                deny_button.click()
        except:
            print("No apareció el mensaje de notificación.")

        # Esperar y hacer clic en botón "Don’t Allow" de Facebook si aparece
        try:
            dont_allow_button = WebDriverWait(driver, 10).until(EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Don’t allow")'
            )))
            if dont_allow_button.is_displayed():
                dont_allow_button.click()
        except:
            print("No apareció el botón 'Don’t allow'.")

        # Validación de acceso correcto
        #post_login_element = wait.until(EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Facebook")')))
        #post_login_element = wait.until(EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Facebook")')))
        #assert post_login_element, "No se validó el acceso correctamente"
        # Validación de acceso correcto mediante el logo de Facebook
        try:
            logo_element = wait.until(EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "Facebook logo")))
            print("Login exitoso: se detectó el logo de Facebook.")
        except TimeoutException:
            print("No se detectó el logo de Facebook tras el login.")
            raise

    finally:
        time.sleep(5)
        driver.quit()