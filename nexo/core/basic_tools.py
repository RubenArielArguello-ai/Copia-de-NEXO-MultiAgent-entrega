import os
import subprocess
from langchain_core.tools import tool


@tool
def leer_archivo(ruta: str) -> str:
    """Lee el contenido de un archivo de texto. Útil para revisar código o documentos existentes."""
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error al leer el archivo: {str(e)}"


@tool
def escribir_archivo(ruta: str, contenido: str) -> str:
    """Escribe contenido en un archivo. Si el archivo no existe, lo crea. Útil para guardar resultados."""
    try:
        # Crea la carpeta si no existe
        os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(contenido)
        return f"Éxito: Archivo escrito en {ruta}"
    except Exception as e:
        return f"Error al escribir el archivo: {str(e)}"


@tool
def ejecutar_codigo_python(codigo: str) -> str:
    """Ejecuta un bloque de código Python y devuelve la salida de la terminal o el error. Útil para hacer cálculos o probar scripts."""
    try:
        # Ejecuta el código en un subproceso y captura la salida
        resultado = subprocess.run(
            ["python3", "-c", codigo], capture_output=True, text=True, timeout=10
        )
        if resultado.returncode == 0:
            return f"Salida:\n{resultado.stdout}"
        else:
            return f"Error de ejecución:\n{resultado.stderr}"
    except Exception as e:
        return f"Error al intentar ejecutar el código: {str(e)}"
