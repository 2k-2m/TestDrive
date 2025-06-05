
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import time
import csv
import random
import os

METRICA_CARGA_APP_A_FEED = "Carga_Feed"
METRICA_PUBLICACION_POST = "Publicacion"
METRICA_ENVIO_MSG_TEXTO = "Ms_Texto"
METRICA_ENVIO_MSG_FOTO = "Ms_Foto"
METRICA_ENVIO_MSG_VIDEO = "Ms_Video"

def obtener_estado_conectividad_real(driver):
    try:
        salida = driver.execute_script("mobile: shell", {
            'command': 'dumpsys connectivity',
            'args': [],
            'includeStderr': True,
            'timeout': 5000
        })['stdout']
        redes_conectadas = []
        for bloque in salida.split("NetworkAgentInfo")[1:]:
            if "state: CONNECTED" in bloque and "VALIDATED" in bloque:
                if "type: WIFI" in bloque:
                    redes_conectadas.append("WIFI")
                elif "type: MOBILE" in bloque:
                    redes_conectadas.append("MOBILE")
        if "WIFI" in redes_conectadas:
            return "WIFI"
        elif "MOBILE" in redes_conectadas:
            return "MOBILE"
        return "SIN_RED"
    except:
        return "SIN_RED"

def setup_driver():
    desired_caps = {
        "platformName": "Android",
        "deviceName": "R58M795NHZF",
        "appPackage": "com.instagram.android",
        "appActivity": "com.instagram.android.activity.MainTabActivity",
        "automationName": "UiAutomator2",
        "forceAppLaunch": True,
        "noReset": True,
        "newCommandTimeout": 360
    }
    options = UiAutomator2Options().load_capabilities(desired_caps)
    try:
        driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
        return driver
    except:
        return None

def guardar_resultado_y_tiempo_en_archivos(tipo_test, ret, lat, lon, inicio, fin, comentario="OK"):
    csv_file = "metricas_instagram.csv"
    txt_file = "tiempos_carga.txt"
    exists = os.path.isfile(csv_file)
    empty = os.path.getsize(csv_file) == 0 if exists else True
    with open(csv_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=';')
        if not exists or empty:
            writer.writerow(["Instagram", "Ret", "Tipo de test", "Latitud", "Longitud", "Fecha_Hora_Inicio", "Fecha_Hora_Fin", "Comentario"])
        writer.writerow(["Instagram", ret, tipo_test, lat, lon, inicio, fin, comentario])
    with open(txt_file, "a", encoding="utf-8") as f:
        f.write(f"{inicio} - {tipo_test}: Inicio: {inicio}, Fin: {fin}, Lat: {lat}, Lon: {lon}, Comentario: {comentario}
")

def get_device_location(driver):
    try:
        loc = driver.location
        return str(loc.get('latitude', 'N/A')), str(loc.get('longitude', 'N/A'))
    except:
        return "N/A", "N/A"

def measure_app_open_to_feed_time(driver):
    try:
        WebDriverWait(driver, 45).until(
            EC.any_of(
                EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/recycler_view")),
                EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/refreshable_container")),
            )
        )
        return True
    except:
        return False

def enter_text_ui(driver, uiautomator, text, desc="", timeout=15):
    try:
        field = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, uiautomator))
        )
        field.clear()
        field.send_keys(text)
        time.sleep(0.5)
        return True
    except:
        return False

def click_button(driver, res_id, desc="", timeout=15, mandatory=True):
    try:
        btn = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().resourceId("{res_id}").enabled(true)'))
        )
        btn.click()
        time.sleep(.5)
        return True
    except:
        if mandatory:
            raise
        return False

def click_tab_icon(driver, res_id, index=0, desc="", timeout=15, mandatory=True):
    try:
        icon = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().resourceId("{res_id}").instance({index}).enabled(true)'))
        )
        icon.click()
        time.sleep(.5)
        return True
    except:
        if mandatory:
            raise
        return False

def is_logged_in(driver):
    try:
        WebDriverWait(driver, 7).until(
            EC.any_of(
                EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/title_logo")),
                EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/feed_tab_icon")),
            )
        )
        return True
    except:
        return False

def find_elements_safely(driver, by, value, timeout=10):
    try:
        WebDriverWait(driver, timeout).until(EC.presence_of_all_elements_located((by, value)))
        return driver.find_elements(by, value)
    except:
        return []

def random_photo(driver, locators):
    for by, value in locators:
        elements = find_elements_safely(driver, by, value)
        filtered = [el for el in elements if "miniatura de foto" in (el.get_attribute("content-desc") or "").lower()]
        if filtered:
            random.choice(filtered).click()
            time.sleep(2)
            return True
    return False

def asegurar_publicacion_activa(driver, timeout=5):
    try:
        btn = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/cam_dest_feed")))
        btn.click()
        return True
    except:
        try:
            WebDriverWait(driver, timeout).until(EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "REEL"))).click()
            btn = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/cam_dest_feed")))
            btn.click()
            return True
        except:
            return False

def select_from_gallery(driver, index, gallery_id="com.instagram.android:id/gallery_grid", class_name="android.widget.CheckBox", timeout=15):
    selector = f'new UiSelector().resourceId("{gallery_id}").childSelector(new UiSelector().className("{class_name}").instance({index}))'
    try:
        thumb = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((AppiumBy.ANDROID_UIAUTOMATOR, selector)))
        thumb.click()
        time.sleep(2)
        return True
    except:
        return False
