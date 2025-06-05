# Versión refactorizada y optimizada del script de automatización Instagram con Appium
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import os, csv, time, random

METRICAS = {
    'feed': "Carga_Feed",
    'post': "Publicacion",
    'msg_texto': "Ms_Texto",
    'msg_foto': "Ms_Foto",
    'msg_video': "Ms_Video"
}

def obtener_estado_conectividad_real(driver):
    try:
        salida = driver.execute_script("mobile: shell", {
            'command': 'dumpsys connectivity', 'args': [], 'includeStderr': True, 'timeout': 5000
        })['stdout']
        if "type: WIFI" in salida and "VALIDATED" in salida:
            return "WIFI"
        if "type: MOBILE" in salida and "VALIDATED" in salida:
            return "MOBILE"
    except:
        pass
    return "SIN_RED"

def setup_driver():
    caps = UiAutomator2Options().load_capabilities({
        "platformName": "Android",
        "deviceName": "AndroidDevice",
        "appPackage": "com.instagram.android",
        "appActivity": "com.instagram.android.activity.MainTabActivity",
        "automationName": "UiAutomator2",
        "noReset": True,
        "newCommandTimeout": 360
    })
    return webdriver.Remote("http://127.0.0.1:4723", options=caps)

def guardar_resultado(tipo_test, ret, lat, lon, inicio, fin, comentario="OK"):
    csv_path, txt_path = "metricas_instagram.csv", "tiempos_carga.txt"
    headers = ["Instagram", "Ret", "Tipo de test", "Latitud", "Longitud", "Fecha_Hora_Inicio", "Fecha_Hora_Fin", "Comentario"]

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=';')
        if os.path.getsize(csv_path) == 0:
            writer.writerow(headers)
        writer.writerow(["Instagram", ret, tipo_test, lat, lon, inicio, fin, comentario])

    with open(txt_path, "a", encoding="utf-8") as f:
        f.write(f"{inicio} - {tipo_test}: Inicio: {inicio}, Fin: {fin}, Lat: {lat}, Lon: {lon}, Comentario: {comentario}\n")

def esperar_elemento(driver, by, value, timeout=15):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))

def esperar_clickable(driver, by, value, timeout=15):
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, value)))

def click(driver, by, value, timeout=15):
    try:
        esperar_clickable(driver, by, value, timeout).click()
        return True
    except:
        return False

def ingresar_texto(driver, by, value, texto, timeout=15):
    try:
        campo = esperar_elemento(driver, by, value, timeout)
        campo.clear()
        campo.send_keys(texto)
        return True
    except:
        return False

def get_location(driver):
    try:
        loc = driver.location
        return str(loc.get('latitude', 'N/A')), str(loc.get('longitude', 'N/A'))
    except:
        return "N/A", "N/A"

def medir_accion(driver, tipo, funcion_accion):
    lat, lon = get_location(driver)
    inicio = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    resultado = funcion_accion()
    fin = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    guardar_resultado(METRICAS[tipo], obtener_estado_conectividad_real(driver), lat, lon, inicio, fin, "OK" if resultado else "Fail")

def test_instagram_automation():
    driver = setup_driver()

    def carga_feed():
        try:
            WebDriverWait(driver, 45).until(EC.presence_of_element_located((AppiumBy.ID, "com.instagram.android:id/recycler_view")))
            return True
        except:
            return False

    medir_accion(driver, 'feed', carga_feed)

    # Otras acciones como login, publicar, enviar mensajes irían con misma estructura

    driver.quit()

if __name__ == "__main__":
    for _ in range(2):
        test_instagram_automation()
