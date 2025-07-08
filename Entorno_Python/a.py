from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException
from datetime import datetime
import subprocess
import csv
import os
import time
import random

# Configuración general
udid = "R58MA32XQQW"
system_port = 8200
appium_port = 4723
archivo_csv = "registro_instagram.csv"

# Inicializar archivo CSV si no existe
if not os.path.isfile(archivo_csv):
    with open(archivo_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            "App", "Red", "Tipo", "Latitud", "Longitud",
            "Fecha Hora Inicio", "Fecha Hora Fin", "Estado",
            "Causa de falla", "Tamaño de archivo (MB)"
        ])

# Función para escribir fila en CSV
def escribir_fila(app, red, tipo, lat, lon, inicio, fin, estado, falla, tamano):
    with open(archivo_csv, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            app, red, tipo, lat, lon,
            inicio.strftime("%Y-%m-%d %H:%M:%S"),
            fin.strftime("%Y-%m-%d %H:%M:%S"),
            estado, falla, tamano
        ])

# Función para cerrar apps
def cerrar_apps(paquetes, udid):
    for pkg in paquetes:
        subprocess.run(["adb", "-s", udid, "shell", "am", "force-stop", pkg])

# Función para iniciar app
def iniciar_app(package, activity, udid):
    os.system(f"adb -s {udid} shell am start -n {package}/{activity}")

# Obtener red
def obtener_red(driver):
    try:
        salida = driver.execute_script("mobile: shell", {
            'command': 'dumpsys connectivity',
            'args': [], 'includeStderr': True, 'timeout': 5000
        })['stdout']
        if "state: CONNECTED" in salida:
            if "type: WIFI" in salida:
                return "WIFI"
            elif "type: MOBILE" in salida:
                return "MOBILE"
        return "SIN_RED"
    except:
        return "SIN_RED"

# Obtener ubicación (si habilitado)
def obtener_ubicacion(driver):
    try:
        loc = driver.location
        return loc['latitude'], loc['longitude']
    except:
        return 0.0, 0.0

# Click si existe elemento
def click_si_existe(driver, metodo, identificador, descripcion="elemento"):
    try:
        elemento = driver.find_element(metodo, identificador)
        elemento.click()
        time.sleep(1)
        return True
    except:
        return False

# Estado conectividad
def obtener_estado_conectividad_real(driver):
    try:
        salida = driver.execute_script("mobile: shell", {
            'command': 'dumpsys telephony.registry | grep mDataConnectionState',
            'args': [], 'includeStderr': True, 'timeout': 5000
        })['stdout']
        if "mDataConnectionState=2" in salida:
            return "MOBILE"
        return "SIN_RED"
    except:
        return "SIN_RED"

# Función principal de prueba Instagram
def test_instagram():
    archivos = ["Video.mp4", "Video2.mp4", "1Imagen.jpg", "2Imagen.jpg", "3Imagen.jpg", "4Imagen.jpg"]

    cerrar_apps(["com.instagram.android"], udid)
    iniciar_app("com.instagram.android", "com.instagram.mainactivity.MainActivity", udid)

    desired_caps = {
        "platformName": "Android",
        "deviceName": udid,
        "udid": udid,
        "automationName": "UiAutomator2",
        "systemPort": system_port,
        "noReset": True
    }

    options = UiAutomator2Options().load_capabilities(desired_caps)
    driver = webdriver.Remote(f"http://127.0.0.1:{appium_port}", options=options)
    driver.implicitly_wait(3)

    try:
        for i in range(1, 9999):
            print(f"\nIteración {i}")
            inicio = datetime.now()
            red = obtener_red(driver)
            lat, lon = obtener_ubicacion(driver)

            # Publicar historia
            try:
                driver.find_element(AppiumBy.XPATH, '//android.widget.FrameLayout[@content-desc="Your story"]/android.view.ViewGroup').click()
                archivo = random.choice(archivos)
                tipo = "Publicar imagen" if archivo.endswith(".jpg") else "Publicar video"
                tamanio = "2 MB" if archivo.endswith(".jpg") else "20 MB"
                index = archivos.index(archivo)
                selector = f'new UiSelector().className("android.widget.FrameLayout").instance({index})'
                driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, selector).click()
                driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Next")').click()
                driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Share")').click()

                # Esperar "Just now"
                success = False
                for _ in range(30):
                    time.sleep(1)
                    try:
                        driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("Just now")')
                        success = True
                        break
                    except:
                        continue
                fin = datetime.now()
                estado, falla = ("exitoso", "") if success else ("fallido", "Timeout")
                escribir_fila("IG", red, tipo, lat, lon, inicio, fin, estado, falla, tamanio)
            except Exception as e:
                fin = datetime.now()
                escribir_fila("IG", red, "Publicar historia", lat, lon, inicio, fin, "fallido", str(e), "0 MB")

            # Visualizar reel
            try:
                click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().description("Reels")')
                inicio_reel = datetime.now()
                red_reel = obtener_estado_conectividad_real(driver)
                lat_reel, lon_reel = obtener_ubicacion(driver)
                time.sleep(5)
                fin_reel = datetime.now()
                escribir_fila("IG", red_reel, "Visualizacion reel", lat_reel, lon_reel, inicio_reel, fin_reel, "exitoso", "", "")
            except Exception as e:
                fin_reel = datetime.now()
                red_reel = obtener_estado_conectividad_real(driver)
                lat_reel, lon_reel = obtener_ubicacion(driver)
                escribir_fila("IG", red_reel, "Visualizacion reel", lat_reel, lon_reel, inicio_reel, fin_reel, "fallido", str(e), "")

            # Enviar mensaje
            try:
                mensaje = "Hola desde Instagram"
                click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().description("Messenger")', "Botón Messenger")
                driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("prueba")').click()
                campo = driver.find_element(AppiumBy.CLASS_NAME, "android.widget.EditText")
                campo.send_keys(mensaje)
                driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().description("Enviar")').click()
                inicio_msg = datetime.now()
                red_msg = obtener_estado_conectividad_real(driver)
                lat_msg, lon_msg = obtener_ubicacion(driver)
                fin_msg = datetime.now()
                escribir_fila("IG", red_msg, "Envio mensaje", lat_msg, lon_msg, inicio_msg, fin_msg, "exitoso", "", f"{len(mensaje)} caracteres")
            except Exception as e:
                fin_msg = datetime.now()
                red_msg = obtener_estado_conectividad_real(driver)
                lat_msg, lon_msg = obtener_ubicacion(driver)
                escribir_fila("IG", red_msg, "Envio mensaje", lat_msg, lon_msg, inicio_msg, fin_msg, "fallido", str(e), "0 caracteres")

            # Enviar imagen
            try:
                click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().description("Agregar contenido multimedia")')
                click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().descriptionContains("Imagen1")')
                click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().description("Enviar")')
                inicio_img = datetime.now()
                red_img = obtener_estado_conectividad_real(driver)
                lat_img, lon_img = obtener_ubicacion(driver)
                time.sleep(2)
                fin_img = datetime.now()
                escribir_fila("IG", red_img, "Envio imagen", lat_img, lon_img, inicio_img, fin_img, "exitoso", "", "2 MB")
            except Exception as e:
                fin_img = datetime.now()
                red_img = obtener_estado_conectividad_real(driver)
                lat_img, lon_img = obtener_ubicacion(driver)
                escribir_fila("IG", red_img, "Envio imagen", lat_img, lon_img, inicio_img, fin_img, "fallido", str(e), "0 MB")

            # Enviar video
            try:
                click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().description("Agregar contenido multimedia")')
                click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().descriptionContains("Video")')
                click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().description("Enviar")')
                inicio_vid = datetime.now()
                red_vid = obtener_estado_conectividad_real(driver)
                lat_vid, lon_vid = obtener_ubicacion(driver)
                time.sleep(3)
                fin_vid = datetime.now()
                escribir_fila("IG", red_vid, "Envio video", lat_vid, lon_vid, inicio_vid, fin_vid, "exitoso", "", "20 MB")
            except Exception as e:
                fin_vid = datetime.now()
                red_vid = obtener_estado_conectividad_real(driver)
                lat_vid, lon_vid = obtener_ubicacion(driver)
                escribir_fila("IG", red_vid, "Envio video", lat_vid, lon_vid, inicio_vid, fin_vid, "fallido", str(e), "0 MB")
            time.sleep(4)

    finally:
        cerrar_apps(["com.instagram.android"], udid)
        driver.quit()

# Bucle principal
if __name__ == "__main__":
    while True:
        test_instagram()
