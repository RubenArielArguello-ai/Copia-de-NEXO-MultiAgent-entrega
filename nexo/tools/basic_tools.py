import re
import ast
import operator
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
        with _project_path(ruta).open("r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error al leer el archivo: {str(e)}"


@tool
def escribir_archivo(ruta: str, contenido: str) -> str:
    """Escribe contenido en un archivo. Si el archivo no existe, lo crea. Útil para guardar resultados."""
    try:
        path = _project_path(ruta)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            f.write(contenido)
        return f"Éxito: Archivo escrito en {ruta}"
    except Exception as e:
        return f"Error al escribir el archivo: {str(e)}"


@tool
def ejecutar_codigo_python(codigo: str) -> str:
    """Evalúa expresiones aritméticas simples sin ejecutar código o procesos."""
    try:
        if len(codigo) > 500:
            raise ValueError("Expresión demasiado larga")
        tree = ast.parse(codigo, mode="eval")
        ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
               ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
               ast.Mod: operator.mod, ast.Pow: operator.pow, ast.USub: operator.neg,
               ast.UAdd: operator.pos}
        def evaluate(node):
            if isinstance(node, ast.Expression): return evaluate(node.body)
            if isinstance(node, ast.Constant) and type(node.value) in (int, float): return node.value
            if isinstance(node, ast.BinOp) and type(node.op) in ops:
                left, right = evaluate(node.left), evaluate(node.right)
                if isinstance(node.op, ast.Pow) and abs(right) > 100: raise ValueError("Exponente fuera de rango")
                result = ops[type(node.op)](left, right)
                if abs(result) > 10**100: raise ValueError("Resultado fuera de rango")
                return result
            if isinstance(node, ast.UnaryOp) and type(node.op) in ops: return ops[type(node.op)](evaluate(node.operand))
            raise ValueError("Solo se permiten operaciones aritméticas")
        return f"Resultado: {evaluate(tree)}"
    except Exception as e:
        return f"Operación rechazada: {type(e).__name__}"
