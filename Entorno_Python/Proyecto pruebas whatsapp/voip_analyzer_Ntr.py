import os
import subprocess
import time
import re
import shutil

# --- CONFIGURACIÓN (AJUSTADA PARA TI) ---

# Ruta en tu celular Huawei. "Memoria interna" es /storage/emulated/0/ para ADB.
PHONE_PCAP_PATH = "/storage/emulated/0/Download/PCAPdroid/"

# El script creará y usará automáticamente la carpeta 'whatsapp_analysis' en tu Escritorio.
# No necesitas cambiar esta línea.
DESKTOP_PATH = os.path.join(os.path.expanduser('~'), 'Desktop')
PC_LOCAL_PATH = os.path.join(DESKTOP_PATH, 'whatsapp_analysis') 

# Intervalo de sondeo en segundos (cada cuánto revisa el script si hay archivos nuevos).
POLL_INTERVAL = 5 

# --- FIN DE LA CONFIGURACIÓN ---

def setup_directories():
    """Crea las carpetas necesarias en el PC si no existen."""
    processed_path = os.path.join(PC_LOCAL_PATH, "processed")
    
    if not os.path.exists(PC_LOCAL_PATH):
        print(f"Creando carpeta de trabajo en tu Escritorio: {PC_LOCAL_PATH}")
        os.makedirs(PC_LOCAL_PATH)
        
    if not os.path.exists(processed_path):
        print(f"Creando subcarpeta para archivos procesados.")
        os.makedirs(processed_path)
    
    return processed_path

def get_remote_files():
    """Obtiene la lista de archivos .pcapng del dispositivo Android."""
    command = f"adb shell ls {PHONE_PCAP_PATH}"
    # Usamos 'timeout' para evitar que el script se cuelgue si el dispositivo se desconecta.
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        print("❌ Error: El comando ADB tardó demasiado. ¿Está el celular conectado y autorizado?")
        return []

    if result.returncode != 0:
        # Silenciamos el error "No such file or directory" que es común antes de la primera captura.
        if "No such file or directory" not in result.stderr:
            print(f"Error al listar archivos en el dispositivo: {result.stderr.strip()}")
        return []
    
    files = [f.strip() for f in result.stdout.splitlines() if f.strip().endswith('.pcapng')]
    return files

def pull_file(filename):
    """Descarga un archivo específico desde el dispositivo al PC."""
    remote_file_path = f"{PHONE_PCAP_PATH}{filename}"
    local_file_path = os.path.join(PC_LOCAL_PATH, filename)
    
    print(f"📥 Descargando '{filename}'...")
    command = f"adb pull \"{remote_file_path}\" \"{local_file_path}\""
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0 or "error" in result.stderr.lower():
        print(f"❌ Error al descargar el archivo: {result.stderr.strip()}")
        return None
        
    print("✅ Descarga completa.")
    return local_file_path

def analyze_pcap(file_path):
    """Analiza un archivo .pcapng con tshark y extrae métricas VoIP."""
    print(f"🔬 Analizando '{os.path.basename(file_path)}'...")
    command = f'tshark -r "{file_path}" -q -z voip,calls'
    
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Error al analizar con TShark: {result.stderr.strip()}")
        return

    print("\n" + "="*25 + " INFORME DE ANÁLISIS " + "="*25)
    print(f"Archivo: {os.path.basename(file_path)}")
    
    output = result.stdout
    if not output.strip() or "=========================" not in output:
         print("\n⚠️ No se encontraron llamadas VoIP válidas en la captura.\n")
         return

    print(output)
    lines = output.splitlines()

    try:
        data_line = lines[-2] 
        stats = re.split(r'\s{2,}', data_line.strip()) # Dividir por 2 o más espacios
        
        # Columnas clave (pueden variar ligeramente, ajusta si es necesario)
        # 0:Start, 1:Stop, 2:Proto, 3:From, 4:To, 5:Pkts, 6:State, 7:Comment
        # 8:Max Jitter, 9:Mean Jitter, 10:Max Delta, 11:Packet Loss
        max_jitter = stats[8]
        mean_jitter = stats[9]
        packet_loss = stats[11]
        
        print("\n--- RESUMEN ---")
        print(f"🟢 Máximo Jitter:     {max_jitter} ms")
        print(f"🔵 Jitter Promedio:    {mean_jitter} ms")
        print(f"🔴 Pérdida de Paquetes: {packet_loss} %")
        print("="*71 + "\n")
    except (IndexError, ValueError):
        print("\n⚠️ No se pudo extraer el resumen. Revisa la tabla de TShark de arriba para verificar el formato.\n")


def main():
    """Función principal del script de monitoreo."""
    print("Iniciando script de análisis automatizado...")
    processed_path = setup_directories()
    processed_files = set()
    
    print("🚀 ¡Listo! El monitor de capturas de WhatsApp está activo.")
    print(f"Vigilando la carpeta del celular: {PHONE_PCAP_PATH}")
    print(f"Los archivos se guardarán en: {PC_LOCAL_PATH}")
    print("Para detener el script, presiona CTRL+C.")

    try:
        while True:
            remote_files = get_remote_files()
            
            new_files = [f for f in remote_files if f not in processed_files]
            
            if new_files:
                for filename in new_files:
                    print("-" * 50)
                    local_path = pull_file(filename)
                    if local_path:
                        analyze_pcap(local_path)
                        shutil.move(local_path, os.path.join(processed_path, filename))
                        print(f"📁 Archivo movido a la carpeta 'processed'.")

                    processed_files.add(filename)
            else:
                print("...esperando nuevos archivos de captura...", end='\r')

            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\n🛑 Script detenido por el usuario. ¡Hasta luego!")
    except Exception as e:
        print(f"\nHa ocurrido un error inesperado: {e}")

if __name__ == "__main__":
    main()