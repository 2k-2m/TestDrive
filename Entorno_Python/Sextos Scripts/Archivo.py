import zipfile
import os

# Crear un archivo de texto con datos aleatorios
with open("dummy.txt", "w") as f:
    f.write("0" * (300 * 1024 * 1024))  # 300 MB de ceros

# Comprimirlo como .zip
with zipfile.ZipFile("archivo_real_300mb.zip", "w") as zipf:
    zipf.write("dummy.txt")

# (opcional) borrar el archivo original
os.remove("dummy.txt")
#✅ Este archivo_real_300mb.zip sí será reconocido por cualquier descompresor como archivo .zip válido.