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


udid = "R58MA32XQQW"  # Cambia al UDID del dispositivo correcto
app = "Facebook"
timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
archivo_csv = f"/media/pi/V/Facebook_Data_{timestamp}.csv"
file_exists = os.path.isfile(archivo_csv)

encabezados = ["App",  "Red", "Type of test", "Latitude", "Longitude", "Initial Time",
    "Final Time", "State", "Cause of failture", "Content Size (MB)"]

def escribir_fila(app , red, tipo, latitud, longitud, inicio, fin, resultado,falla,tamanio):
    fila = [app, red, tipo, latitud, longitud,
            inicio.strftime("%Y-%m-%d %H:%M:%S"),
            fin.strftime("%Y-%m-%d %H:%M:%S"),
            resultado, falla, tamanio]
    with open(archivo_csv, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=',')
        if f.tell() == 0:
            writer.writerow(encabezados)
        writer.writerow(fila)

def iniciar_app(package_name, activity_name, udid):
    comando = f"adb -s {udid} shell am start -n {package_name}/{activity_name}"
    resultado = os.system(comando)
    if resultado == 0:
        print(f"App {package_name} iniciada en {udid}")
    else:
        print(f" Error al iniciar {package_name} en {udid}")
        
def cerrar_todas_las_apps(paquetes, udid):
    for paquete in paquetes:
        subprocess.run(['adb', '-s', udid, 'shell', 'am', 'force-stop', paquete])
        print(f"App {paquete} cerrada en {udid}.")

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
            return "WiFi"
        elif "MOBILE" in redes_conectadas:
            return "Mobile"
        else:
            return "Disconnected"

    except Exception as e:
        print(f"Error al verificar conectividad real: {e}")
        return "Disconnected"

def verificar_envio_sent(driver, wait, bounds_real):
    try:
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
            result = "Successful"
            falla = ""
            verificacion = True
            print(f"Enviado correctamente.")
            return time, result, falla, verificacion
        else:
            print("No se detectó confirmación de envío ('Sent').")
            time = datetime.now()
            result = "Failed"
            falla = "Timeout"
            verificacion = False
            return time, result, falla, verificacion
    except TimeoutException:
        print("No se detectó confirmación de envío ('Sent').")
        time = datetime.now()
        result = "Failed"
        falla = "Timeout"
        verificacion = False
        return time, result, falla, verificacion
 
    
def click_en_primer_archivo_disponible(driver, max_intentos=5):
    
    for i in range(0, 5 + max_intentos):
        try:
            selector = f'new UiSelector().resourceId("com.android.documentsui:id/icon_thumb").instance({i})'
            elemento = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, selector)
            if elemento.get_attribute("enabled") == "true":
                print(f"[INFO] Archivo encontrado en instancia {i}, haciendo click.")
                elemento.click()
                return True
            else:
                print(f"[DEBUG] Instancia {i} encontrada pero no habilitada.")
        except NoSuchElementException:
            print(f"[DEBUG] No se encontró el elemento en instancia {i}.")
    print("[ERROR] No se encontró ningún archivo habilitado para hacer click.")
    return False


def obtener_tamano_por_fecha_desde_desc(desc, extension,carpeta="/sdcard/Download"):
    try:
        if not desc.lower().startswith("photo taken "):
            raise ValueError("El content-desc no es una foto válida")
        fecha_raw = desc.replace("Photo taken ", "").strip()  # Ej: "Jun 2, 2025"
        fecha_dt = datetime.strptime(fecha_raw, "%b %d, %Y")  # "Jun 2, 2025"
        fecha_formateada = fecha_dt.strftime("%Y-%m-%d")       # "2025-06-02"
        # Listar archivos con detalle
        comando = f'adb shell ls -l {carpeta}/*{extension}'
        salida = subprocess.getoutput(f'adb -s {udid} shell ls -ltlh /sdcard/Download/*.jpg')
        lineas = salida.strip().split('\n')

        for linea in lineas:
            partes = linea.split()
            
            if len(partes) >= 7:
                fecha_archivo = f"{partes[5]}"
                
                if fecha_archivo == fecha_formateada:
                    archivo = partes[-1]
                    ruta_completa = f"{archivo}"
                    # Obtener tamaño legible
                    salida_tamano = subprocess.getoutput(f'adb -s {udid} shell ls -lh "{ruta_completa}"')
                    columnas = salida_tamano.strip().split()
                    if len(columnas) >= 5:
                        tamano = columnas[4]
                        print(f"[INFO] Archivo: {archivo}, Tamaño: {tamano}")
                        return tamano
                
        print("[WARN] No se encontró imagen con esa fecha.")
        return "0.0"

    except Exception as e:
        print(f"[ERROR] No se pudo obtener tamaño de la imagen: {e}")
        return "0.0"


def test_login_facebook():
    
    cerrar_todas_las_apps(["com.facebook.katana", "com.facebook.orca"], udid)

    # 2. Lanza manualmente la app (no login, solo abrir)
    iniciar_app("com.facebook.katana", "com.facebook.katana.LoginActivity", udid)

    desired_caps = {
        "platformName": "Android",
        "deviceName": "R58MA32XQQW",
        "udid": udid,
        "appPackage": "com.facebook.katana",
        "automationName": "UiAutomator2",
        "systemPort": 8201,
        "noReset": True
    }

    options = UiAutomator2Options().load_capabilities(desired_caps)
    driver = webdriver.Remote("http://127.0.0.1:4725", options=options)
    driver.implicitly_wait(3) 
    wait = WebDriverWait(driver, 10) 

    try:
        ##### FEED #####
        inicio_feed = datetime.now()
        latitude_feed, longitude_feed, _ = obtener_ubicacion(driver)
        red_feed = obtener_estado_conectividad_real(driver)
        if red_feed == "Disconnected":
            fin_feed = datetime.now()
            resultado = "Failed"
            falla = "Item no found"
            tamanio = ""
            escribir_fila(app, red_feed, "Feed loading", latitude_feed, longitude_feed, inicio_feed, fin_feed, resultado, falla, tamanio)
        else:
            feed_elements = driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR,
                                                'new UiSelector().className("android.view.ViewGroup").instance(16)')
            if feed_elements:
                fin_feed = datetime.now()
                resultado = "Successful"
                falla = ""
                tamanio = ""
                print("Primer grupo del feed cargado correctamente. (instance)")
            else:
                fin_feed = datetime.now()
                resultado = "Failed"
                falla = "Item no found"
                tamanio = ""
            escribir_fila(app, red_feed, "Feed loading", latitude_feed, longitude_feed, inicio_feed, fin_feed, resultado, falla, tamanio)
            
        #### CREATE STORY ####
        click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                                  'new UiSelector().description("Create story")', "Botón Create Story")
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
            if red_story == "Disconnected":
                resultado = "Failed"
                fin_story = datetime.now()
                falla = "No service"
                tamanio = "0.0"
                escribir_fila(app,red_story,"Story upload", latitude_story, longitude_story, inicio_story, fin_story, resultado, falla, tamanio)

            else: 
                max_espera = 15
                polling_interval = 0.5 
                espera_total = 0

                while espera_total < max_espera:
                    uploading_indicator = driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR,
                                                            'new UiSelector().descriptionContains("Sharing…, Uploading").instance(1)')
                    if not uploading_indicator:
                        break
                    time.sleep(polling_interval)
                    espera_total += polling_interval
                resultado = "Successful" if espera_total < max_espera else "Failed"
                falla = "" if espera_total < max_espera else "Timeout"
                tamanio = "2.0" if espera_total < max_espera else "0.0"
        else:
            resultado = "Failed"
            falla = "Item no found"
            tamanio = "0.0"
        fin_story = datetime.now()
        escribir_fila(app,red_story,"Story upload", latitude_story, longitude_story, inicio_story, fin_story, resultado, falla, tamanio)
        ######## REPRODUCCION DE VIDEO CORTO ########
        video = click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                    'new UiSelector().descriptionMatches("^Video.*")', 
                    "Botón Video")
        if video == False:
            click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                    'new UiSelector().className("android.widget.FrameLayout").instance(12)', 
                    "Botón Video")
        progreso_detectado = False
        tiempo_inicio = time.time()
        red_video_corto = obtener_estado_conectividad_real(driver)
        latitude_video_corto, longitude_video_corto,_ = obtener_ubicacion(driver)
        inicio_video_corto = datetime.now()
        
        if red_video_corto == "Disconnected":
            fin_video_corto = datetime.now()
            resultado = "Failed"
            falla = "No service"
            tamanio = ""
            print("Red no disponible, carga de video corto fallido.")
        else: 
            while time.time() - tiempo_inicio < 15:
                try:
                    driver.find_element(AppiumBy.CLASS_NAME, "android.widget.ProgressBar")
                    progreso_detectado = True
                    break  
                except:
                    pass
                time.sleep(0.1)  
            if progreso_detectado:
                fin_video_corto = datetime.now()
                resultado = "Failed"
                falla = "TimeOut"
                tamanio = ""
                print("Video corto reproducido sin éxito (progress bar detectado)")
            else:
                fin_video_corto = datetime.now()
                resultado = "Successful"
                falla = ""
                tamanio = ""
                print("Video corto reproducido con éxito (sin progress bar)")
                
        escribir_fila(app, red_video_corto, "Short video playback", latitude_video_corto, longitude_video_corto, inicio_video_corto, fin_video_corto, resultado, falla, tamanio)     
        click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                    'new UiSelector().description("Home, tab 1 of 6")', 
                    "Botón Home")
        
        # Mandar mensaje
        try:
            mensaje = "Hola"
            click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                            'new UiSelector().description("Messaging")', "Botón Messaging")
            contacto_btn = driver.find_element(AppiumBy.XPATH, '//androidx.recyclerview.widget.RecyclerView[@resource-id="com.facebook.orca:id/(name removed)"]/android.widget.Button')
            
            contacto_btn.click()
            campo_mensaje = driver.find_element(AppiumBy.CLASS_NAME, "android.widget.EditText")
            campo_mensaje.send_keys(mensaje)
            click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                                'new UiSelector().description("Send")', "Botón Send")
            campo_mensaje = driver.find_element(AppiumBy.CLASS_NAME, "android.widget.EditText")
            campo_mensaje.send_keys(mensaje)
            if click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                                'new UiSelector().description("Send")', "Botón Send"):
                inicio_msg = datetime.now()
                red_msg = obtener_estado_conectividad_real(driver)
                if red_msg == "Disconnected":
                    fin_msg = datetime.now()
                    latitude_msg, longitude_msg,_ = obtener_ubicacion(driver)
                    resultado = "Failed"
                    falla = "No service"
                    tamanio = "0 caracteres"
                    print("Red no disponible después de enviar, mensaje fallido.")
                else:
                    latitude_msg, longitude_msg, _ = obtener_ubicacion(driver)
                    fin_msg, resultado, falla, verificacion = verificar_envio_sent(driver, wait, "[945,2003][1027,2050]")
                    if verificacion:
                        tamanio = str(len(mensaje)) + " caracteres"
                    else:
                        tamanio = "0 caracteres"
            else:
                fin_msg = datetime.now()
                latitude_msg, longitude_msg,_ = obtener_ubicacion(driver)
                red_msg = obtener_estado_conectividad_real(driver)
                resultado = "Failed"
                falla = "Item no found"
                tamanio = "0 caracteres"
            escribir_fila(app, red_msg, "Message sending", latitude_msg, longitude_msg, inicio_msg, fin_msg, resultado, falla, tamanio)
        
        except Exception as e:
            print(f"Error en MESSAGE: {e}")
            fin_msg = datetime.now()
            resultado = "Failed"
            falla = "Item no found"
            tamanio = "0 caracteres"
            red_msg = obtener_estado_conectividad_real(driver)
            escribir_fila(app, red_msg,"Message sending", latitude_msg, longitude_msg, inicio_msg, fin_msg, resultado, falla, tamanio)
            
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

                if red_photo == "Disconnected":
                    fin_photo = datetime.now()
                    latitude_photo, longitude_photo,_ = obtener_ubicacion(driver)
                    resultado = "Failed"
                    falla = "No service"
                    tamanio = "0.0"
                    print("Red no disponible después de intentar enviar foto.")
                else:
                    latitude_photo, longitude_photo, _ = obtener_ubicacion(driver)
                    fin_photo, resultado, falla, verificacion = verificar_envio_sent(driver, wait,"[945,1347][1027,1394]")
                    if verificacion:
                        elemento = driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().description("Photo taken Jun 2, 2025")')
                        desc = elemento.get_attribute("content-desc")
                        tamanio = "2.0"
                    else: 
                        tamanio = "0.0"

            else:
                inicio_photo = datetime.now()
                fin_photo = datetime.now()
                latitude_photo, longitude_photo,_ = obtener_ubicacion(driver)
                red_photo = obtener_estado_conectividad_real(driver)
                resultado = "Failed"
                falla = "Item no found"
                tamanio = "0.0"

            escribir_fila(app, red_photo, "Image sending", latitude_photo, longitude_photo, inicio_photo, fin_photo, resultado, falla, tamanio)

        except Exception as e:
            print(f"Error en PHOTO: {e}")
            fin_photo = datetime.now()
            resultado = "Failed"
            falla = "Item no found"
            tamanio = "0.0"
            red_photo = obtener_estado_conectividad_real(driver)
            escribir_fila(app,red_photo,"Image sending", latitude_photo, longitude_photo, inicio_photo, fin_photo, resultado, falla, tamanio)




        # Ejecuta el comando ADB para listar archivos .jpg con detalles, ordenados por fecha
        salida = subprocess.getoutput('adb shell ls -ltlh /sdcard/Download/*.jpg')
        # Procesa línea por línea
        matriz_tamanos = []
        for linea in salida.strip().split('\n'):
            columnas = linea.split()
            if len(columnas) >= 5:
                tamano = columnas[4]  # Tamaño legible (KB, MB)
                matriz_tamanos.append(tamano)
        # Mostrar los resultados
        print("[INFO] Tamaños de archivos JPG:")
        for i, t in enumerate(matriz_tamanos, start=1):
            print(f"{i}. {t}")




        ##### VIDEO #####
        try:
            driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR,'new UiSelector().description("Video recorded Jun 5, 2025, 00:12")')
            
            click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                            'new UiSelector().description("Video recorded Jun 5, 2025, 00:12")', "Video")
            
            if click_si_existe(driver, AppiumBy.XPATH,
                            '//android.widget.ImageButton[@content-desc="Back"]', "Video atrás"):
                inicio_video = datetime.now()
                fin_video = datetime.now()
                latitude_video, longitude_video,_ = obtener_ubicacion(driver)
                red_video = obtener_estado_conectividad_real(driver)
                resultado = "Failed"
                tamanio = "0.0"
                falla = "Item no found"
            else: 
            
                if click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                                'new UiSelector().text("Send")', "Botón Send Video"):

                    inicio_video = datetime.now()
                    red_video = obtener_estado_conectividad_real(driver)

                    if red_video == "Disconnected":
                        fin_video = datetime.now()
                        latitude_video, longitude_video,_ = obtener_ubicacion(driver)
                        resultado = "Failed"
                        tamanio = "0.0"
                        falla = "No service"
                        print("Red no disponible después de intentar enviar video.")
                    else:
                        latitude_video, longitude_video, _ = obtener_ubicacion(driver)
                        fin_video, resultado, falla, verificacion = verificar_envio_sent(driver, wait, "[945,852][1027,899]")
                        if verificacion:
                            tamanio = obtener_tamano_por_fecha_desde_desc(desc,"mp4")
                        else: 
                            tamanio = "0.0"

                else:
                    inicio_video = datetime.now()
                    fin_video = datetime.now()
                    latitude_video, longitude_video,_ = obtener_ubicacion(driver)
                    red_video = obtener_estado_conectividad_real(driver)
                    resultado = "Failed"
                    tamanio = "0.0"
                    falla = "Item no found"

            escribir_fila(app, red_video, "Video sending", latitude_video, longitude_video, inicio_video, fin_video, resultado, falla, tamanio)

        except Exception as e:
            print(f"Error en VIDEO: {e}")
            inicio_video = datetime.now()
            fin_video = datetime.now()
            latitude_video, longitude_video,_ = obtener_ubicacion(driver)
            red_video = obtener_estado_conectividad_real(driver)
            resultado = "Failed"
            tamanio = "0.0"
            falla = "Item no found"
            escribir_fila(app, red_video, "Video sending", latitude_video, longitude_video, inicio_video, fin_video, resultado, falla, tamanio)

        ##### FILE #####
        try:
            click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                            'new UiSelector().description("Show more options.")', "Botón Open more actions")
            click_si_existe(driver, AppiumBy.ANDROID_UIAUTOMATOR,
                            'new UiSelector().text("Files")', "Botón Files")

            if click_en_primer_archivo_disponible(driver):


                inicio_file = datetime.now()
                red_file = obtener_estado_conectividad_real(driver)

                if red_file == "Disconnected":
                    fin_file = datetime.now()
                    latitude_file, longitude_file,_ = obtener_ubicacion(driver)
                    resultado = "Failed"
                    falla = "No service"
                    tamanio = "0.0"
                    print("Red no disponible después de intentar enviar archivo.")
                else:
                    latitude_file, longitude_file, _ = obtener_ubicacion(driver)
                    fin_file, resultado, falla, verificacion = verificar_envio_sent(driver, wait,"[945,2003][1027,2050]")
                    if verificacion:
                        tamanio = "1.27"
                    else: 
                        tamanio = "0.0"

            else:
                inicio_file = datetime.now()
                fin_file = datetime.now()
                latitude_file, longitude_file,_ = obtener_ubicacion(driver)
                red_file = obtener_estado_conectividad_real(driver)
                resultado = "Failed"
                falla = "Item no found"
                tamanio = "0.0"

            escribir_fila(app, red_file, "File sending", latitude_file, longitude_file, inicio_file, fin_file, resultado, falla, tamanio)

        except Exception as e:
            print(f"Error en FILE: {e}")
            inicio_file = datetime.now()
            fin_file = datetime.now()
            latitude_file, longitude_file,_ = obtener_ubicacion(driver)
            red_file = obtener_estado_conectividad_real(driver)
            resultado = "Failed"
            falla = "Item no found"
            tamanio = "0.0"
            escribir_fila(app, red_file, "File sending", latitude_file, longitude_file, inicio_file, fin_file, resultado, falla, tamanio)

    finally:  
        paquetes_a_cerrar = [
            "com.facebook.katana",   
            "com.facebook.orca",     
        ]
        cerrar_todas_las_apps(paquetes_a_cerrar, udid)
        driver.quit()
        print("Reinicio app...\n")
        test_login_facebook()
        
test_login_facebook()
