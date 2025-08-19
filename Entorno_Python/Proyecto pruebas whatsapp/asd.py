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

def leer_configuracion(path_txt):
    configuraciones = []
    parametros = {"tiempo_entre_ciclos": 0, "mensaje": 0}      # 0 ->desactivado, 1->activado  
    lectura_parametros = False
    with open(path_txt, 'r') as f:
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
            if len(partes) != 3:
                continue
            contacto, tiempo_espera, tipo = partes
            configuraciones.append((contacto, int(tiempo_espera), tipo.strip().lower()))
    return configuraciones, parametros

#CST → Tiempo de establecimiento (Call Setup Time)
#CSFR → Tasa de fallos de inicio (Call Setup Failure Rate)
#CDR (o DCR) → Tasa de llamadas caídas (Call Drop Rate)

def inicializar_csv_si_no_existe(archivo_csv):
    if not os.path.exists(archivo_csv):
        with open(archivo_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                "App", "Red", "Type of test",
                "Latitude","Longitude", "Initial Time", "Final Time",
                "State","Cause of failure","Content Size (MB)"
            ])


def principal():
    configuraciones, parametros = leer_configuracion("/home/pi/Desktop/Finale/configuracion.txt")
    TIEMPO_ENTRE_CICLOS = parametros.get("tiempo_entre_ciclos", 0)
    MENSAJE_ALEATORIO   = parametros.get("mensaje", 0)


def medir_cst(driver, wait, contacto, espera, archivo_csv):
    # T0: botón llamar; T1: estado "en llamada" detectado
    # log CSV con setup_time_s y SUCCESS/FAIL
    ...

def medir_csfr(driver, wait, contacto, espera, archivo_csv):
    # Intentar conectar dentro de un timeout; si no conecta -> FAIL
    ...

def medir_cdr(driver, wait, contacto, espera, archivo_csv):
    # Conectar y sostener X s; si se corta antes -> DROP
    ...

HANDLERS = {
    "cst":  medir_cst,
    "csfr": medir_csfr,
    "cd":   medir_cdr,
    "cdr":  medir_cdr,
    "texto": lambda d,w,c,e,csv: ...,      # si luego lo usas
    "imagen": lambda d,w,c,e,csv: ...,     # idem
    # etc.
}


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