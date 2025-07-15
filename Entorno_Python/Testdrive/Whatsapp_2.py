import csv
import time
from datetime import datetime
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import os
import random
import re
from collections import defaultdict
import signal

detener = False

def manejar_senal(sig, frame):
    global detener
    print("\n Señal de interrupción recibida. Terminando ciclo de forma segura...")
    detener = True
signal.signal(signal.SIGINT, manejar_senal)  # Ctrl+C

def leer_configuraciones(path_txt):
    configuraciones = []
    parametros = {"TIEMPO_ENTRE_CICLOS": 0,
                  "MENSAJE_ALEATORIO": 0      # 0 ->desactivado, 1->activado                                
    }  # 5 como valor por defecto

    lectura_parametros = False
    with open(path_txt, 'r', encoding='utf-8') as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            if linea.startswith("#PARAMETROS"):
                lectura_parametros=True
                continue
            if linea.startswith("#CONTACTOS"):
                lectura_parametros = False
                continue
            if lectura_parametros:
                if "=" in linea:
                    clave, valor = linea.split("=", 1)
                    parametros[clave.strip()] = int(valor.strip())
                continue

            partes = linea.split("|")
            if len(partes) != 4:
                continue
            contacto, mensaje, tiempo_espera, tipo = partes
            configuraciones.append((contacto, mensaje, int(tiempo_espera), tipo.strip().lower()))
    return configuraciones, parametros

def agrupar_config_por_contacto(configuraciones):
    agrupadas = defaultdict(list)
    for contacto, mensaje, espera, tipo in configuraciones:
        agrupadas[contacto].append((mensaje, espera, tipo))
    return agrupadas

def inicializar_csv_si_no_existe(archivo_csv):
    if not os.path.exists(archivo_csv):
        with open(archivo_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                "App", "Red", "Type of test",
                "Latitude","Longitude", "Initial Time", "Final Time",
                "State","Case of failure","Content Size (MB)"
            ])

def enviar_mensaje_texto(driver, wait, mensaje):
    print(" Enviando mensaje de texto...")
    driver.find_element(AppiumBy.ID, "com.whatsapp:id/entry").send_keys(mensaje)
    driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Enviar").click()
    print(" Mensaje de texto enviado.")

def enviar_imagen_recientes(driver, wait, aleatorio=False):
    print("️ Enviando imagen...")

    # Paso 1: Abrir galería desde botón "Adjuntar"
    wait.until(EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "Adjuntar"))).click()
    time.sleep(1)
    wait.until(EC.presence_of_element_located(
        (AppiumBy.ID, "com.whatsapp:id/pickfiletype_gallery_holder"))).click()

    try:
        # Paso 2: Esperar a que cargue la vista de galería reciente
        wait.until(EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/gallery_view_pager")))
        print(" Vista 'Recientes' cargada correctamente.")

        # Paso 3: Buscar todos los elementos que son imágenes en recientes
        elementos = driver.find_elements(AppiumBy.ID, "com.whatsapp:id/unsupported_media_item_view")

        # Filtrar aquellos con content-desc que contenga "foto"
        imagenes = [e for e in elementos if "foto" in (e.get_attribute("content-desc") or "").lower()]

        if not imagenes:
            print("️ No se encontraron imágenes con descripción 'foto'. Usando todos los elementos.")
            imagenes = elementos

        if imagenes:
            print(f" Total imágenes encontradas: {len(imagenes)}")
            if aleatorio:
                seleccionada = random.choice(imagenes)
            else:
                seleccionada= imagenes[0]
            print(" Imagen seleccionada aleatoriamente.")
            seleccionada.click()

            # Esperar botón de envío y enviarla
            wait.until(EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/send_media_btn"))).click()
            wait.until(EC.invisibility_of_element_located((AppiumBy.ID, "com.whatsapp:id/send_media_btn")))
            print(" Imagen enviada correctamente.")
        else:
            raise Exception(" No se encontraron imágenes para enviar en Recientes.")

    except Exception as e:
        raise Exception(f" Error al seleccionar imagen: {e}")

def enviar_video_recientes(driver, wait, aleatorio=False):
    print("️ Enviando video...")

    # Paso 1: Abrir galería desde botón "Adjuntar"
    wait.until(EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "Adjuntar"))).click()
    time.sleep(1)
    wait.until(EC.presence_of_element_located(
        (AppiumBy.ID, "com.whatsapp:id/pickfiletype_gallery_holder"))).click()

    try:
        # Paso 2: Esperar vista de galería "Recientes"
        wait.until(EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/gallery_view_pager")))
        print(" Vista 'Recientes' cargada correctamente.")

        # Paso 3: Buscar elementos tipo video
        elementos = driver.find_elements(AppiumBy.ID, "com.whatsapp:id/unsupported_media_item_view")

        # Filtrar por aquellos que tengan "video" en content-desc
        videos = [e for e in elementos if "video" in (e.get_attribute("content-desc") or "").lower()]

        if not videos:
            raise Exception(" No se encontraron videos en Recientes.")

        print(f" Videos encontrados: {len(videos)}")

        if aleatorio:
            seleccionado = random.choice(videos)
            print(" Video seleccionado aleatoriamente.")
        else:
             seleccionado = videos[0]   
        seleccionado.click()

        # Esperar y hacer click en el botón de envío
        wait.until(EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/send_media_btn"))).click()
        wait.until(EC.invisibility_of_element_located((AppiumBy.ID, "com.whatsapp:id/send_media_btn")))
        print("Video enviado correctamente.")

    except Exception as e:
        raise Exception(f" Error al seleccionar video: {e}")

def enviar_documento(driver, wait):
    print("Enviando documento...")

    # Paso 1: Abrir menú de adjuntar y seleccionar opción Documento
    wait.until(EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "Adjuntar"))).click()
    time.sleep(1)
    wait.until(EC.presence_of_element_located(
        (AppiumBy.ID, "com.whatsapp:id/pickfiletype_document_holder"))).click()

    try:
        # Paso 2: Esperar a que cargue lista de archivos recientes
        wait.until(EC.presence_of_element_located((AppiumBy.ID, "android:id/list")))
        items = driver.find_elements(AppiumBy.ID, "com.whatsapp:id/document_picker_item")

        if not items:
            raise Exception(" No se encontraron elementos en la lista de documentos.")

        print(f"Total elementos encontrados: {len(items)}")

        # Paso 3: Filtrar solo documentos PDF, DOC, TXT
        documentos_validos = []
        for item in items:
            try:
                nombre = item.find_element(AppiumBy.ID, "com.whatsapp:id/title").text.lower()
                if any(nombre.endswith(ext) for ext in [".pdf", ".doc", ".docx", ".txt"]):
                    documentos_validos.append(item)
            except Exception:
                continue

        if not documentos_validos:
            raise Exception("No se encontraron documentos válidos (PDF, DOC, TXT).")

        print(f"Documentos válidos encontrados: {len(documentos_validos)}")
        seleccionado = random.choice(documentos_validos)
        print("Documento seleccionado aleatoriamente.")
        seleccionado.click()

        # Paso 4: Esperar y hacer clic en botón de envío
        wait.until(EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/send"))).click()
        print("Documento enviado correctamente.")

    except Exception as e:
        raise Exception(f"Error durante el envío de documento: {e}")

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
    except Exception:
        return ""

def obtener_gps(driver):
    try:
        location = driver.location
        lat = str(location.get('latitude', ''))
        lon = str(location.get('longitude', ''))
        return lat, lon
    except Exception:
        return "", ""
################################
def registrar_tiempo_carga_app(driver, fecha_inicio, fecha_fin, resultado, archivo_csv,type_of_failure):
    app = "WhatsApp"
    tipo_contenido = "Feed loading"

    lat, lon = obtener_gps(driver)
    red = obtener_estado_conectividad_real(driver)

    fila = [
        app,
        red,
        tipo_contenido,
        lat or "",
        lon or "",
        fecha_inicio.strftime("%d/%m/%Y %H:%M:%S"),
        fecha_fin.strftime("%d/%m/%Y %H:%M:%S"),
        resultado,
        type_of_failure,
        ""  # tamaño archivo
    ]

    with open(archivo_csv, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(fila)

    print("Registro de tiempo de carga almacenado en CSV.")

def evaluar_estado_mensaje(driver, contacto, tipo_accion, tiempo_inicio_total, start_envio, tiempo_max_espera, archivo_csv, tamano_mb=""):
    from datetime import datetime

    app = "WhatsApp"

    fecha_hora_inicio_envio = datetime.now()
    lat, lon = obtener_gps(driver)
    red = obtener_estado_conectividad_real(driver)

    fecha_hora_fin_envio = ""
    fecha_hora_inicio_entrega = ""
    fecha_hora_fin_entrega = ""
    resultado = "Failed"
    type_of_failure = ""

    print(f"Estado de red: {red}")
    print("Esperando estado del mensaje...")

    for _ in range(tiempo_max_espera):
        time.sleep(1)
        iconos = driver.find_elements(AppiumBy.ID, "com.whatsapp:id/status")
        if not iconos:
            continue

        estado = iconos[-1].get_attribute("content-desc")

        if estado == "Esperando":
            resultado = "Failed"
            type_of_failure = "Timeout"
            if red == "Disconnected":
                type_of_failure = "No service"
                print("Sin red activa. Cancelando espera.")
                break

        elif estado == "Enviado":
            if fecha_hora_fin_envio == "":
                fecha_hora_fin_envio = datetime.now()
                resultado = "Successful"
                type_of_failure = ""

        elif estado == "Entregado":
            if fecha_hora_fin_envio == "":
                fecha_hora_fin_envio = datetime.now()
            if fecha_hora_inicio_entrega == "":
                fecha_hora_inicio_entrega = datetime.now()
            fecha_hora_fin_entrega = datetime.now()
            resultado = "Successful"
            type_of_failure = ""
            break

    # Validación final por timeout
    if resultado == "Enviado" and fecha_hora_inicio_entrega == "":
        if red != "Disconnected":
            resultado = "Failed"
            type_of_failure = "Timeout"

    elif resultado == "Reloj" and red != "Disconnected":
        resultado = "Failed"
        type_of_failure = "Timeout"

    fila = [
        app,
        red,
        tipo_accion + " sendig",
        lat or "",
        lon or "",
        fecha_hora_inicio_envio.strftime("%d/%m/%Y %H:%M:%S"),
        fecha_hora_fin_envio.strftime("%d/%m/%Y %H:%M:%S") if fecha_hora_fin_envio != "" else "",
        resultado,
        type_of_failure,
        round(tamano_mb, 4) if isinstance(tamano_mb, float) else ""
    ]
    with open(archivo_csv, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(fila)
        
    fila = [
        app,
        red,
        tipo_accion +" receiving",
        lat or "",
        lon or "",
        fecha_hora_inicio_entrega.strftime("%d/%m/%Y %H:%M:%S") if fecha_hora_inicio_entrega != "" else "",
        fecha_hora_fin_entrega.strftime("%d/%m/%Y %H:%M:%S") if fecha_hora_fin_entrega != "" else "",
        resultado,
        type_of_failure,
        round(tamano_mb, 4) if isinstance(tamano_mb, float) else ""
    ]

    with open(archivo_csv, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(fila)

    print("Registro almacenado en CSV.")

def ejecutar_bloque_contacto(driver, wait, contacto, pruebas, archivo_csv, aleatorio= False):
    print(f"Iniciando bloque de pruebas para contacto: {contacto}")
    if not seleccionar_contacto(driver, wait, contacto):
        print(f"No se pudo abrir el chat con {contacto}. Saltando bloque.\n")
        return

    for mensaje, espera, tipo_contenido in pruebas:
        if tipo_contenido == "add_estado":
            continue  
        try:
            tiempo_inicio_total = time.time()
            print(f"Ejecutando: {tipo_contenido}")

            if tipo_contenido == "texto":
                enviar_mensaje_texto(driver, wait, mensaje)
                start_envio = time.time()
                tamano_mb = len(mensaje.encode('utf-8')) / (1024 * 1024)
                evaluar_estado_mensaje(driver, contacto, "Message", tiempo_inicio_total, start_envio, espera, archivo_csv, tamano_mb=tamano_mb)
            
            elif tipo_contenido in ["imagen", "video", "documento"]:
                nombre_archivo, tamano_mb = enviar_archivo_desde_documentos(driver, wait, tipo_contenido, aleatorio= aleatorio)
                start_envio = time.time()  # ✅ agregar esto
                contenido = {
                    "imagen": "Image",
                    "video": "Video",
                    "documento": "File"
                }.get(tipo_contenido, "Unknown")
                evaluar_estado_mensaje(driver, contacto, contenido, tiempo_inicio_total, start_envio, espera, archivo_csv, tamano_mb=tamano_mb)

            else:
                print(f"Tipo de contenido no soportado: {tipo_contenido}")
                continue

        except Exception as e:
            print(f"Error en acción '{tipo_contenido}': {e}")
################################
def medir_tiempo_carga_app(driver, wait):
    try:
        driver.terminate_app("com.whatsapp")
        driver.activate_app("com.whatsapp")
        fecha_inicio = datetime.now()

        wait.until(EC.presence_of_element_located((AppiumBy.XPATH, "//android.widget.TextView[@text='Chats']")))
        fecha_fin = datetime.now()

        print("WhatsApp cargado correctamente")
        return True, fecha_inicio, fecha_fin

    except TimeoutException:
        print("WhatsApp no cargó correctamente.")
        fecha_error = datetime.now()
        return False, fecha_error, fecha_error
    
def seleccionar_contacto(driver, wait, nombre_contacto):
    try:
        print("Buscando contacto directamente desde la lista de chats (pantalla principal)...")
        time.sleep(1)

        candidatos = driver.find_elements(AppiumBy.ID, "com.whatsapp:id/contact_row_container")
        print(f"Candidatos encontrados en lista de chats: {len(candidatos)}")

        for idx, candidato in enumerate(candidatos):
            try:
                nombre = candidato.find_element(AppiumBy.ID, "com.whatsapp:id/conversations_row_contact_name").text
                print(f"{idx+1}. Nombre detectado: {nombre} | Clickable: {candidato.get_attribute('clickable')} | Focusable: {candidato.get_attribute('focusable')}")

                if nombre_contacto.lower() in nombre.lower():
                    print(f"Clic sobre el resultado #{idx+1} - {nombre}")
                    candidato.click()
                    try:
                        wait.until(EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/entry")))
                        print(f"Chat de '{nombre_contacto}' abierto correctamente (con campo de entrada visible).")
                        return True
                    except TimeoutException:
                        print("Este resultado abrió una vista sin campo de entrada. Volviendo atrás...")
                        driver.back()
                        time.sleep(1.5)
                        continue

            except Exception as e:
                print(f"Error procesando candidato #{idx+1}: {e}")
                continue

        print(f"Ningún resultado válido abrió el chat principal de '{nombre_contacto}'.")
        return False

    except Exception as e:
        print(f"Error crítico al buscar contacto: {e}")
        return False
#######################
def publicar_estado_imagen(driver, wait, tiempo_max_espera, archivo_csv):
    from datetime import datetime

    app = "Whatsapp"
    tipo_contenido = "Story upload"
    resultado = "Failed"
    fecha_hora_inicio = None
    fecha_hora_fin = None

    lat, lon = obtener_gps(driver)
    red = obtener_estado_conectividad_real(driver)

    try:
        print("Navegando a pestaña 'Novedades'...")
        wait.until(EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "Novedades"))).click()

        # Verificar si hay estado fallido ("No se pudo enviar") y eliminarlo
        try:
            elementos = driver.find_elements(AppiumBy.ID, "com.whatsapp:id/date_time")
            for e in elementos:
                if "no se pudo enviar" in (e.text or "").lower():
                    print("Estado fallido detectado. Intentando eliminar...")

                    contenedores = driver.find_elements(AppiumBy.ID, "com.whatsapp:id/status_content")
                    if contenedores:
                        driver.long_press(contenedores[0])  # Long click
                        time.sleep(1)

                        boton_borrar = wait.until(EC.presence_of_element_located(
                            (AppiumBy.ACCESSIBILITY_ID, "Eliminar")))
                        boton_borrar.click()

                        confirmar = wait.until(EC.presence_of_element_located(
                            (AppiumBy.ID, "android:id/button1")))
                        confirmar.click()
                        time.sleep(2)
                        print("Estado fallido eliminado correctamente.")
                    else:
                        print("No se encontró contenedor para eliminar el estado fallido.")
                    break
        except Exception as e:
            print(f"No se pudo eliminar estado fallido: {e}")

        print("Haciendo click en ícono cámara...")
        wait.until(EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/fab"))).click()

        print("Cargando galería...")
        wait.until(EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/gallery_view_pager")))
        imagenes = driver.find_elements(AppiumBy.ID, "com.whatsapp:id/unsupported_media_item_view")
        imagenes_fotos = [e for e in imagenes if "foto" in (e.get_attribute("content-desc") or "").lower()]
        if not imagenes_fotos:
            imagenes_fotos = imagenes
        if not imagenes_fotos:
            raise Exception("No se encontraron imágenes disponibles.")
        random.choice(imagenes_fotos).click()

        print("Enviando imagen como estado...")
        boton_enviar = wait.until(EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/send")))
        fecha_hora_inicio = datetime.now()
        boton_enviar.click()

        print("Esperando cambio de texto a 'Justo ahora'...")
        detectado = False #Bandera para romper el for _ in
        for _ in range(tiempo_max_espera):
            time.sleep(1)
            elementos = driver.find_elements(AppiumBy.ID, "com.whatsapp:id/date_time")
            for e in elementos:
                texto = e.text.lower().strip()
                print(f"Texto detectado: {texto}")

                if "justo ahora" in texto:
                    fecha_hora_fin = datetime.now()
                    resultado = "Successful"
                    type_of_failure = ""
                    detectado = True
                    break
            if detectado:
                break

        if not detectado:
            resultado = "Failed"
            if red == "Disconnected":
                type_of_failure = "No Service"
            else:
                type_of_failure = "Timeout"
            fecha_hora_fin = datetime.now()

    except Exception as e:
        print(f"Error en publicación de estado: {e}")
        if not fecha_hora_inicio:
            fecha_hora_inicio = datetime.now()
        if not fecha_hora_fin:
            fecha_hora_fin = datetime.now()
        resultado = "Failed"
        type_of_failure = "Item no found"

    finally:
        print("Regresando a pantalla principal...")
        driver.back()  # Solo uno
        time.sleep(1.5)
        fila = [
            app,
            red,
            tipo_contenido,
            lat or "",
            lon or "",
            fecha_hora_inicio.strftime("%d/%m/%Y %H:%M:%S") if fecha_hora_inicio else "",
            fecha_hora_fin.strftime("%d/%m/%Y %H:%M:%S") if fecha_hora_fin else "",
            resultado,
            type_of_failure,
            ""
        ]

        with open(archivo_csv, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(fila)

        print("Publicación registrada en CSV.")

def enviar_archivo_desde_documentos(driver, wait, tipo_archivo_deseado="documento",aleatorio=False):
    
    print(f"Enviando archivo como '{tipo_archivo_deseado}' desde Documentos...")

    # Paso 1: Abrir adjuntar → Documento
    wait.until(EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "Adjuntar"))).click()
    time.sleep(1)
    wait.until(EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/pickfiletype_document_holder"))).click()

    # Paso 2: Esperar a que se cargue la lista de archivos
    wait.until(EC.presence_of_element_located((AppiumBy.ID, "android:id/list")))
    items = driver.find_elements(AppiumBy.ID, "com.whatsapp:id/document_picker_item")

    extensiones = {
        "imagen": [".jpg", ".jpeg", ".png"],
        "video": [".mp4", ".mov", ".avi"],
        "documento": [".pdf", ".doc", ".docx", ".txt"]
    }

    seleccionables = []
    for item in items:
        try:
            nombre_elem = item.find_element(AppiumBy.ID, "com.whatsapp:id/title")
            tamano_elem = item.find_element(AppiumBy.ID, "com.whatsapp:id/size")

            nombre = nombre_elem.text.strip()
            tamano_texto = tamano_elem.text.strip()

            # Filtrar por tipo de archivo
            if any(nombre.lower().endswith(ext) for ext in extensiones[tipo_archivo_deseado]):
                # Extraer tamaño en MB como número flotante
                match = re.match(r"([\d.]+)\s*MB", tamano_texto.upper())
                tamano_mb = float(match.group(1)) if match else ""

                seleccionables.append((item, nombre, tamano_mb))
        except Exception as e:
            continue

    if not seleccionables:
        raise Exception(f"No se encontraron archivos tipo '{tipo_archivo_deseado}' en Documentos.")

    print(f"Archivos filtrados ({tipo_archivo_deseado}): {len(seleccionables)}")

    # Paso 3: Selección aleatoria
    seleccionado, nombre_archivo, tamano_mb = (random.choice(seleccionables) if aleatorio else seleccionables [0])
    seleccionado.click()

    # Paso 4: Esperar y hacer clic en botón de envío
    wait.until(EC.presence_of_element_located((AppiumBy.ID, "com.whatsapp:id/send"))).click()
    wait.until(EC.invisibility_of_element_located((AppiumBy.ID, "com.whatsapp:id/send")))
    print(f"Archivo '{nombre_archivo}' enviado correctamente. Tamaño: {tamano_mb} MB")

    return nombre_archivo, tamano_mb
    
timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
ARCHIVO_RESULTADO = f"/media/pi/V/WhatsApp_Data_{timestamp}.csv"

def main():
    
    inicializar_csv_si_no_existe(ARCHIVO_RESULTADO)

    while not detener:
        print("\nIniciando nuevo ciclo de pruebas...")

        configuraciones, parametros = leer_configuraciones("/home/pi/Desktop/Testdrive/configuracion.txt")
        TIEMPO_ENTRE_CICLOS = parametros.get("TIEMPO_ENTRE_CICLOS", 0)
        MENSAJE_ALEATORIO = parametros.get("MENSAJE_ALEATORIO", 0)

        
        options = UiAutomator2Options().load_capabilities({
            "platformName": "Android",
            "deviceName": "RF8MB0G4KTJ",  # Este puede ser cualquier nombre, pero...
            "udid": "RF8MB0G4KTJ",        # Este ES obligatorio si hay más de un dispositivo

            "automationName": "UiAutomator2",
            "appPackage": "com.whatsapp",
            "appActivity": "com.whatsapp.HomeActivity",

            "systemPort": 8202,          # DEBE ser diferente para cada dispositivo
            "noReset": True
        })

        driver = webdriver.Remote("http://localhost:4727", options=options)
        wait = WebDriverWait(driver, 10)

        try:
            cargado, fecha_inicio, fecha_fin = medir_tiempo_carga_app(driver, wait)
            if not cargado:
                registrar_tiempo_carga_app(driver, fecha_inicio, fecha_fin, "Failed", ARCHIVO_RESULTADO, "Timeout")
                raise Exception("WhatsApp no cargó correctamente.")
            else:
                registrar_tiempo_carga_app(driver, fecha_inicio, fecha_fin, "Successful", ARCHIVO_RESULTADO, "")

            pruebas_por_contacto = agrupar_config_por_contacto(configuraciones)

            #Publicar estado si está programado (solo una vez)
            estado_publicado = False
            for contacto, pruebas in pruebas_por_contacto.items():
                #if MENSAJE_ALEATORIO:
                #    random.shuffle(pruebas)
                for mensaje, espera, tipo_contenido in pruebas:
                    if tipo_contenido == "add_estado" and not estado_publicado:
                        print(f"Ejecutando publicación de estado para: {contacto}")
                        publicar_estado_imagen(driver, wait, espera, ARCHIVO_RESULTADO) 
                        estado_publicado = True
                        break
                if estado_publicado:
                    break

            # Ejecutar pruebas por contacto
            for contacto, pruebas in pruebas_por_contacto.items():
                if detener:
                    break
                if MENSAJE_ALEATORIO:
                    random.shuffle(pruebas)
                ejecutar_bloque_contacto(driver, wait, contacto, pruebas, ARCHIVO_RESULTADO, aleatorio=MENSAJE_ALEATORIO) ####

        except Exception as e:
            print(f"Error general en el ciclo: {e}")
        finally:
            try:
                driver.quit()
            except:
                print("No fue posible cerrar correctamente el driver.")
            print(f"WhatsApp cerrado")
            if not detener:
                print(f"Esperando {TIEMPO_ENTRE_CICLOS} segundos para reiniciar...")
                time.sleep(TIEMPO_ENTRE_CICLOS)

if __name__ == "__main__":
    main()
