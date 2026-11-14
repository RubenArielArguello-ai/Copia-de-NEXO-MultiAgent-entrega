import os
import re
import subprocess
from pathlib import Path
from nexo.tools.base_tool import BaseTool
from langchain_core.tools import tool


_QUOTED_CONTENT = re.compile(r"\"([\s\S]*?)\"|'([\s\S]*?)'|`([\s\S]*?)`|“([\s\S]*?)”")


def extract_requested_file_content(request: str) -> str | None:
    """Extract an explicit file payload without asking a model to rewrite it."""
    if not isinstance(request, str):
        return None

    matches = list(_QUOTED_CONTENT.finditer(request))
    for match in matches:
        prefix = request[max(0, match.start() - 100):match.start()]
        clause = re.split(r"[,;\n]", prefix)[-1]
        if re.search(r"\b(?:contenido|texto|exactamente|literalmente)\b", clause, re.IGNORECASE):
            return next(group for group in match.groups() if group is not None)

    marker = re.search(
        r"\b(?:contenido|texto)(?:\s+(?:exacto|literal|literalmente))?\s*(?::|=|\bes\b)?\s*",
        request,
        re.IGNORECASE,
    )
    if marker:
        value = request[marker.end():]
        value = re.split(r"\s+(?:y\s+)?(?:luego|después|despues|then)\b", value, maxsplit=1, flags=re.IGNORECASE)[0]
        return value.strip() or None

    if len(matches) == 1 and re.search(
        r"\b(?:escribe|escribir|escribí|escriba|write|guardar|guarda|guarde)\b",
        request[:matches[0].start()], re.IGNORECASE,
    ):
        return next(group for group in matches[0].groups() if group is not None)
    return None


class FileReadTool(BaseTool):
    """Lee archivos de texto dentro del directorio de trabajo de NEXO."""
    @property
    def name(self): return "file_read"

    @property
    def description(self): return "Lee un archivo de texto dentro del directorio del proyecto NEXO."

    def execute(self, context: dict) -> dict:
        path = _project_path(context.get("path", ""))
        with path.open("r", encoding="utf-8", newline="") as file:
            content = file.read()
        return {"output": {"path": str(path), "content": content}}


class FileWriteTool(BaseTool):
    """Crea o reemplaza un archivo de texto dentro del directorio de trabajo."""
    @property
    def name(self): return "file_write"

    @property
    def description(self): return "Crea o escribe un archivo de texto dentro del directorio del proyecto NEXO."

    def execute(self, context: dict) -> dict:
        path = _project_path(context.get("path", ""))
        content = context.get("content")
        if not isinstance(content, str):
            raise ValueError("El contenido del archivo debe ser texto")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            file.write(content)
        return {"output": {"path": str(path), "content": content}}


def _project_path(value: str) -> Path:
    if not value:
        raise ValueError("Se requiere una ruta de archivo")
    base = Path.cwd().resolve()
    path = Path(value).expanduser()
    path = (path if path.is_absolute() else base / path).resolve()
    if path != base and base not in path.parents:
        raise ValueError("La ruta debe permanecer dentro del directorio de trabajo de NEXO")
    return path


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
