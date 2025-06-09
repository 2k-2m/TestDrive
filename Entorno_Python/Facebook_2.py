from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import time
import csv
import os
import subprocess
from datetime import datetime
import random
import subprocess

archivo_csv = "registro_facebook.csv"
file_exists = os.path.isfile(archivo_csv)

encabezados = [
    "App",  "RED", "Type", "Latitud", "Longitud", "Fecha Hora Inicio",
    "Fecha Hora Fin", "Estado", "Causa de falla", "Tamanio de archivo (MB)"
]

def escribir_fila(app , red, tipo, latitud, longitud, inicio, fin, resultado,falla,tamanio):
    fila = [
        app, red, tipo, latitud, longitud,
        inicio.strftime("%Y-%m-%d %H:%M:%S"),
        fin.strftime("%Y-%m-%d %H:%M:%S"),
        resultado, falla, tamanio
    ]
    with open(archivo_csv, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=';')
        if f.tell() == 0:
            writer.writerow(encabezados)
        writer.writerow(fila)

def cerrar_todas_las_apps(paquetes):
    for paquete in paquetes:
        subprocess.run(['adb', 'shell', 'am', 'force-stop', paquete])
        print(f"App {paquete} cerrada.")

def obtener_ubicacion(driver):
    try:
        loc = driver.location
        return loc['latitude'], loc['longitude'], loc['altitude']
    except:
        return 0, 0, 0


def click_si_existe(driver, by, selector, desc="Elemento"):
    try:
        el = driver.find_element(by, selector)
        el.click()
        print(f"{desc} clickeado.")
        return True
    except NoSuchElementException:
        print(f"{desc} no encontrado.")
        return False
    
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
        else:
            return "SIN_RED"

    except Exception as e:
        print(f"Error al verificar conectividad real: {e}")
        return "SIN_RED"

def verificar_envio_sent(driver, wait, bounds_real):
    try:
        # Esperar hasta 5 segundos a que aparezca el elemento con bounds específicos
        wait = WebDriverWait(driver, 10)
        
        def condicion(d):
            try:
                el = d.find_element(AppiumBy.XPATH, '//android.view.ViewGroup[@content-desc="Sent "]')
                bounds = el.get_attribute("bounds")
                print(f"[INFO] bounds encontrados: {bounds}")
                return bounds == bounds_real
            except:
                return False

        sent_confirm = wait.until(condicion)
        
        if sent_confirm:
            time = datetime.now()
            result = "exitoso"
            falla = ""
            verificacion = True
            print(f"Enviado correctamente.")
            return time, result, falla, verificacion
        else:
            print("No se detectó confirmación de envío ('Sent').")
            time = datetime.now()
            result = "fallido"
            falla = "Time Out"
            verificacion = False
            return time, result, falla, verificacion
    except TimeoutException:
        print("No se detectó confirmación de envío ('Sent').")
        time = datetime.now()
        result = "fallido"
        falla = "Time Out"
        verificacion = False
        return time, result, falla, verificacion


def test_login_facebook():
    desired_caps = {
        "platformName": "Android",
        "deviceName": "R58MA32XQQW",
        "appPackage": "com.facebook.katana",
        "automationName": "UiAutomator2",
        "noReset": True
    }

    options = UiAutomator2Options().load_capabilities(desired_caps)
    driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
    driver.implicitly_wait(3) 
    wait = WebDriverWait(driver, 10) 

    try:
        ##### FEED #####
        inicio_feed = datetime.now()
        latitude_feed, longitude_feed, _ = obtener_ubicacion(driver)
        red_feed = obtener_estado_conectividad_real(driver)
        # Verificar si no hay red antes de continuar
        if red_feed == "SIN_RED":
            fin_feed = datetime.now()
            resultado = "fallido"
            falla = "Sin red"
            tamanio = ""
            escribir_fila("FB", red_feed, "Carga feed", latitude_feed, longitude_feed, inicio_feed, fin_feed, resultado, falla, tamanio)
        else:
            feed_elements = driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR,
                                                'new UiSelector().className("android.view.ViewGroup").instance(16)')
            if feed_elements:
                fin_feed = datetime.now()
                resultado = "exitoso"
                falla = ""
                tamanio = ""
                print("Primer grupo del feed cargado correctamente. (instance)")
            else:
                fin_feed = datetime.now()
                resultado = "fallido"
                falla = "Elemento no encontrado"
                tamanio = ""
            
            escribir_fila("FB", red_feed, "Carga feed", latitude_feed, longitude_feed, inicio_feed, fin_feed, resultado, falla, tamanio)
            
        #### CREATE STORY ####
        click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                                  'new UiSelector().description("Create story")', "Botón Create Story")
        # Verificar permisos (ejemplo: Access Camera Roll)
        click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                        'new UiSelector().description("Continue")', "Botón Continue")
        click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                        'new UiSelector().text("ALLOW")', "Botón ALLOW")
        photos = driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR,
                              'new UiSelector().descriptionContains("Photo")')

        if photos:
            fotos_disponibles = photos[:5]
            foto_random = random.choice(fotos_disponibles)
            foto_random.click()
            print("Imagen aleatoria seleccionada correctamente.")
            
            
            click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                            'new UiSelector().description("Share")', "Botón Share")
            click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                        'new UiSelector().text("NOT NOW")', "Botón NOT NOW")
            print("Esperando que termine la subida de la historia...")
            inicio_story = datetime.now()
            latitude_story, longitude_story, _ = obtener_ubicacion(driver)
            red_story = obtener_estado_conectividad_real(driver)
            if red_story == "SIN_RED":
                resultado = "fallido"
                fin_story = datetime.now()
                falla = "Sin red"
                tamanio = "0 MB"
                escribir_fila("FB",red_story,"Publicar historia", latitude_story, longitude_story, inicio_story, fin_story, resultado, falla, tamanio)

            else: 
                max_espera = 15  # Segundos máx de espera (ajústalo si es necesario)
                polling_interval = 0.5  # Cada cuánto verificamos
                espera_total = 0

                while espera_total < max_espera:
                    uploading_indicator = driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR,
                                                            'new UiSelector().descriptionContains("Sharing…, Uploading").instance(1)')
                    if not uploading_indicator:
                        break
                    time.sleep(polling_interval)
                    espera_total += polling_interval
                resultado = "exitoso" if espera_total < max_espera else "fallido"
                falla = "" if espera_total < max_espera else "Time Out"
                tamanio = "2 MB" if espera_total < max_espera else "0 MB"
        else:
            resultado = "fallido"
            falla = "Elemento no encontrado"
            tamanio = "0 MB"
        fin_story = datetime.now()
        escribir_fila("FB",red_story,"Publicar historia", latitude_story, longitude_story, inicio_story, fin_story, resultado, falla, tamanio)

        
        # Mandar mensaje
        try:
            click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                            'new UiSelector().description("Messaging")', "Botón Messaging")
            contacto_btn = driver.find_element(AppiumBy.XPATH, '//androidx.recyclerview.widget.RecyclerView[@resource-id="com.facebook.orca:id/(name removed)"]/android.widget.Button')
            
            contacto_btn.click()
            campo_mensaje = driver.find_element(AppiumBy.CLASS_NAME, "android.widget.EditText")
            campo_mensaje.send_keys("Hola")
            click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                                'new UiSelector().description("Send")', "Botón Send")
            campo_mensaje = driver.find_element(AppiumBy.CLASS_NAME, "android.widget.EditText")
            campo_mensaje.send_keys("Hola")
            if click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                                'new UiSelector().description("Send")', "Botón Send"):
                inicio_msg = datetime.now()
                red_msg = obtener_estado_conectividad_real(driver)
                # Verificar red justo después de intentar enviar
                if red_msg == "SIN_RED":
                    fin_msg = datetime.now()
                    latitude_msg, longitude_msg,_ = obtener_ubicacion(driver)
                    resultado = "fallido"
                    falla = "Sin red"
                    tamanio = "0 caracteres"
                    print("Red no disponible después de enviar, mensaje fallido.")
                else:
                    latitude_msg, longitude_msg, _ = obtener_ubicacion(driver)
                    fin_msg, resultado, falla, verificacion = verificar_envio_sent(driver, wait, "[945,2003][1027,2050]")
                    if verificacion:
                        tamanio = "4 caracteres"
                    else:
                        tamanio = "0 caracteres"
            else:
                fin_msg = datetime.now()
                latitude_msg, longitude_msg,_ = obtener_ubicacion(driver)
                red_msg = obtener_estado_conectividad_real(driver)
                resultado = "fallido"
                falla = "Elemento no encontrado"
                tamanio = "0 caracteres"
            escribir_fila("FB", red_msg, "Envio de mensaje", latitude_msg, longitude_msg, inicio_msg, fin_msg, resultado, falla, tamanio)
        
        except Exception as e:
            print(f"Error en MESSAGE: {e}")
            fin_msg = datetime.now()
            resultado = "fallido"
            falla = "Elemento no encontrado"
            tamanio = "0 caracteres"
            red_msg = obtener_estado_conectividad_real(driver)
            escribir_fila("FB", red_msg,"Envio de mensaje", latitude_msg, longitude_msg, inicio_msg, fin_msg, resultado, falla, tamanio)
            
            
        ##### PHOTO #####
        try:
            click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                            'new UiSelector().description("Open photo gallery.")', "Botón Choose photo")
            click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                            'new UiSelector().description("Photo taken Jun 2, 2025").instance(0)', "Imagen")
            
            if click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                            'new UiSelector().text("Send")', "Botón Send Imagen"):

                inicio_photo = datetime.now()
                red_photo = obtener_estado_conectividad_real(driver)

                if red_photo == "SIN_RED":
                    fin_photo = datetime.now()
                    latitude_photo, longitude_photo,_ = obtener_ubicacion(driver)
                    resultado = "fallido"
                    falla = "Sin red"
                    tamanio = "0 MB"
                    print("Red no disponible después de intentar enviar foto.")
                else:
                    latitude_photo, longitude_photo, _ = obtener_ubicacion(driver)
                    fin_photo, resultado, falla, verificacion = verificar_envio_sent(driver, wait,"[945,1347][1027,1394]")
                    if verificacion:
                        tamanio = "2 MB"
                    else: 
                        tamanio = "0 MB"

            else:
                inicio_photo = datetime.now()
                fin_photo = datetime.now()
                latitude_photo, longitude_photo,_ = obtener_ubicacion(driver)
                red_photo = obtener_estado_conectividad_real(driver)
                resultado = "fallido"
                falla = "Elemento no encontrado"
                tamanio = "0 MB"

            escribir_fila("FB", red_photo, "Envio de foto", latitude_photo, longitude_photo, inicio_photo, fin_photo, resultado, falla, tamanio)

        except Exception as e:
            print(f"Error en PHOTO: {e}")
            fin_photo = datetime.now()
            resultado = "fallido"
            falla = "Elemento no encontrado"
            tamanio = "0 MB"
            red_photo = obtener_estado_conectividad_real(driver)
            escribir_fila("FB",red_photo,"Envio de foto", latitude_photo, longitude_photo, inicio_photo, fin_photo, resultado, falla, tamanio)
            
        # Enviar videos
        ##### VIDEO #####
        try:
            click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                            'new UiSelector().description("Video recorded Jun 5, 2025, 00:12")', "Video")
            if click_si_existe(driver, AppiumBy.XPATH,
                            '//android.widget.ImageButton[@content-desc="Back"]', "Video atrás"):
                inicio_video = datetime.now()
                fin_video = datetime.now()
                latitude_video, longitude_video,_ = obtener_ubicacion(driver)
                red_video = obtener_estado_conectividad_real(driver)
                resultado = "fallido"
                tamanio = "0 MB"
                falla = "Elemento no encontrado"
            else: 
            
                if click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                                'new UiSelector().text("Send")', "Botón Send Video"):

                    inicio_video = datetime.now()
                    red_video = obtener_estado_conectividad_real(driver)

                    if red_video == "SIN_RED":
                        fin_video = datetime.now()
                        latitude_video, longitude_video,_ = obtener_ubicacion(driver)
                        resultado = "fallido"
                        tamanio = "0 MB"
                        falla = "Sin red"
                        print("Red no disponible después de intentar enviar video.")
                    else:
                        latitude_video, longitude_video, _ = obtener_ubicacion(driver)
                        fin_video, resultado, falla, verificacion = verificar_envio_sent(driver, wait, "[945,852][1027,899]")
                        if verificacion:
                            tamanio = "25.58 MB"
                        else: 
                            tamanio = "0 MB"

                else:
                    inicio_video = datetime.now()
                    fin_video = datetime.now()
                    latitude_video, longitude_video,_ = obtener_ubicacion(driver)
                    red_video = obtener_estado_conectividad_real(driver)
                    resultado = "fallido"
                    tamanio = "0 MB"
                    falla = "Elemento no encontrado"

            escribir_fila("FB", red_video, "Envio de video", latitude_video, longitude_video, inicio_video, fin_video, resultado, falla, tamanio)

        except Exception as e:
            print(f"Error en VIDEO: {e}")
            inicio_video = datetime.now()
            fin_video = datetime.now()
            latitude_video, longitude_video,_ = obtener_ubicacion(driver)
            red_video = obtener_estado_conectividad_real(driver)
            resultado = "fallido"
            tamanio = "0 MB"
            falla = "Elemento no encontrado"
            escribir_fila("FB", red_video, "Envio de video", latitude_video, longitude_video, inicio_video, fin_video, resultado, falla, tamanio)

        ##### FILE #####
        try:
            click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                            'new UiSelector().description("Show more options.")', "Botón Open more actions")
            click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                            'new UiSelector().text("Files")', "Botón Files")

            if click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                            'new UiSelector().className("android.widget.LinearLayout").instance(5)', "Archivo"):

                inicio_file = datetime.now()
                red_file = obtener_estado_conectividad_real(driver)

                if red_file == "SIN_RED":
                    fin_file = datetime.now()
                    latitude_file, longitude_file,_ = obtener_ubicacion(driver)
                    resultado = "fallido"
                    falla = "Sin red"
                    tamanio = "0 Mb"
                    print("Red no disponible después de intentar enviar archivo.")
                else:
                    latitude_file, longitude_file, _ = obtener_ubicacion(driver)
                    fin_file, resultado, falla, verificacion = verificar_envio_sent(driver, wait,"[945,2003][1027,2050]")
                    if verificacion:
                        tamanio = "1.27 MB"
                    else: 
                        tamanio = "0 MB"

            else:
                inicio_file = datetime.now()
                fin_file = datetime.now()
                latitude_file, longitude_file,_ = obtener_ubicacion(driver)
                red_file = obtener_estado_conectividad_real(driver)
                resultado = "fallido"
                falla = "Elemento no encontrado"
                tamanio = "0 Mb"

            escribir_fila("FB", red_file, "Envio de documento", latitude_file, longitude_file, inicio_file, fin_file, resultado, falla, tamanio)

        except Exception as e:
            print(f"Error en FILE: {e}")
            inicio_file = datetime.now()
            fin_file = datetime.now()
            latitude_file, longitude_file,_ = obtener_ubicacion(driver)
            red_file = obtener_estado_conectividad_real(driver)
            resultado = "fallido"
            falla = "Elemento no encontrado"
            tamanio = "0 Mb"
            escribir_fila("FB", red_file, "Envio de documento", latitude_file, longitude_file, inicio_file, fin_file, resultado, falla, tamanio)

    finally:
        # Cierra todas las apps necesarias
        paquetes_a_cerrar = [
            "com.facebook.katana",   # Facebook
            "com.facebook.orca",     # Messenger
            # Añade aquí otros paquetes si los estás usando
        ]
        cerrar_todas_las_apps(paquetes_a_cerrar)
        driver.quit()
        print("Reinicio app...\n")
        test_login_facebook()
test_login_facebook()