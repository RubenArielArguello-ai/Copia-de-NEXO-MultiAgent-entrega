"""
NEXO — Marco de seguridad y ejecución de herramientas.

Proporciona:
- Definición de esquemas de parámetros (ToolParameter)
- Política de seguridad y prevención de inyección de comandos
- Ejecución segura con validación de tipos, captura de excepciones y timeouts
- Registro centralizado de herramientas autorizadas
"""

from __future__ import annotations
import re
import time
import logging
import queue
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)
_TOOL_RUNTIME_LOCK = threading.Lock()


# ──────────────────────────────────────────────────────────────────────
# Política de Seguridad
# ──────────────────────────────────────────────────────────────────────

DANGEROUS_SHELL_PATTERNS = re.compile(r'[;&|`$<>()\\\[\]\n\r]')

DISALLOWED_BINARIES = {
    "rm", "sudo", "su", "dd", "mkfs", "kill", "pkill", "killall",
    "chmod", "chown", "mv", "sh", "bash", "zsh", "csh", "exec",
    "eval", "python", "perl", "ruby", "nc", "netcat", "wget"
}

ALLOWED_SYSTEM_COMMANDS = {
    "ifconfig", "ip", "netstat", "ping", "sw_vers", "uname", "uptime",
    "ps", "vm_stat", "sysctl"
}


class SecurityPolicy:
    """Valida que comandos y parámetros no contengan vectores de inyección."""

    @staticmethod
    def is_safe_string(value: str) -> bool:
        """Verifica que un string no contenga metacaracteres peligrosos de shell."""
        if not isinstance(value, str):
            return True
        return not bool(DANGEROUS_SHELL_PATTERNS.search(value))

    @staticmethod
    def validate_command(cmd_tokens: list[str]) -> tuple[bool, Optional[str]]:
        """Verifica que una lista de tokens de comando sea segura y esté autorizada."""
        if not cmd_tokens:
            return False, "Comando vacío"

        binary = cmd_tokens[0].strip().lower()
        # Si viene con ruta (/sbin/ifconfig), tomar el basename
        binary_base = binary.split("/")[-1]

        if binary_base in DISALLOWED_BINARIES:
            return False, f"Comando '{binary_base}' está expresamente prohibido por política de seguridad"

        if binary_base not in ALLOWED_SYSTEM_COMMANDS:
            return False, f"Comando '{binary_base}' no pertenece a la lista de herramientas del sistema autorizadas"

        # Validar que ningún argumento contenga inyección
        for arg in cmd_tokens[1:]:
            if not SecurityPolicy.is_safe_string(arg):
                return False, f"Argumento contiene caracteres peligrosos: '{arg}'"

        return True, None


# ──────────────────────────────────────────────────────────────────────
# Esquema de Parámetros
# ──────────────────────────────────────────────────────────────────────

@dataclass
class ToolParameter:
    """Define un parámetro aceptado por una herramienta."""
    name:           str
    type:           type
    required:       bool               = False
    default:        Any                = None
    description:    str                = ""
    allowed_values: Optional[list[Any]] = None

    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        if value is None:
            if self.required:
                return False, f"El parámetro '{self.name}' es obligatorio."
            return True, None

        if not isinstance(value, self.type):
            return False, f"Parámetro '{self.name}' debe ser de tipo {self.type.__name__}, recibido {type(value).__name__}."

        if isinstance(value, str) and not SecurityPolicy.is_safe_string(value):
            return False, f"Parámetro '{self.name}' contiene caracteres no permitidos."

        if self.allowed_values is not None and value not in self.allowed_values:
            return False, f"Parámetro '{self.name}' debe ser uno de {self.allowed_values}, recibido '{value}'."

        return True, None


# ──────────────────────────────────────────────────────────────────────
# Clase Base de Herramienta
# ──────────────────────────────────────────────────────────────────────

class BaseTool(ABC):
    """Interfaz segura y uniforme para todas las herramientas de NEXO."""

    is_safe:         bool = True
    timeout_seconds: int  = 15

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre único de la herramienta."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Descripción de qué hace la herramienta."""

    @property
    def parameters(self) -> dict[str, ToolParameter]:
        """Esquema de parámetros aceptados. Por defecto vacío."""
        return {}

    def validate_parameters(self, params: dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Valida los parámetros de entrada contra el esquema."""
        for name, param_def in self.parameters.items():
            val = params.get(name, param_def.default)
            ok, err = param_def.validate(val)
            if not ok:
                return False, err
        return True, None

    @abstractmethod
    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Lógica concreta de ejecución de la herramienta.
        Debe ser implementada por cada subclase.
        """

    def safe_execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Punto de entrada seguro:
        1. Valida parámetros de contexto
        2. Ejecuta con captura de excepciones
        3. Enforcea timeout
        4. Registra métricas de ejecución
        """
        t0 = time.time()
        tool_name = self.name

        # Validación de parámetros
        ok, err = self.validate_parameters(context)
        if not ok:
            logger.warning("[TOOL] Parameter validation failed for '%s': %s", tool_name, err)
            return {
                "tool":      tool_name,
                "success":   False,
                "error":     f"Validación de parámetros fallida: {err}",
                "output":    {},
                "duration_ms": 0.0,
            }

        with _TOOL_RUNTIME_LOCK:
            if getattr(self, "_execution_active", False):
                return {"tool": tool_name, "success": False, "error": "Una ejecución de esta herramienta sigue activa", "output": {}, "duration_ms": 0.0}
            self._execution_active = True
        outcome: queue.Queue = queue.Queue(maxsize=1)

        def invoke():
            try:
                outcome.put((True, self.execute(context)))
            except BaseException as exc:
                outcome.put((False, exc))
            finally:
                with _TOOL_RUNTIME_LOCK:
                    self._execution_active = False

        worker = threading.Thread(target=invoke, name=f"nexo-tool-{tool_name}", daemon=True)
        worker.start()
        worker.join(max(0.01, float(self.timeout_seconds)))
        elapsed_ms = (time.time() - t0) * 1000
        if worker.is_alive():
            logger.error("[TOOL] Timed out executing '%s' after %.2fs", tool_name, self.timeout_seconds)
            return {"tool": tool_name, "success": False,
                    "error": f"Tiempo límite excedido ({self.timeout_seconds}s)",
                    "output": {}, "duration_ms": round(elapsed_ms, 2), "timed_out": True}
        try:
            succeeded, result = outcome.get_nowait()
        except queue.Empty:
            return {"tool": tool_name, "success": False, "error": "La herramienta terminó sin resultado",
                    "output": {}, "duration_ms": round(elapsed_ms, 2)}
        if not succeeded:
            logger.error("[TOOL] Exception executing '%s': %s", tool_name, type(result).__name__)
            return {"tool": tool_name, "success": False, "error": f"Error interno: {type(result).__name__}",
                    "output": {}, "duration_ms": round(elapsed_ms, 2)}
        if not isinstance(result, dict):
            result = {"output": result}
        result["tool"] = tool_name
        result["success"] = result.get("success", True)
        result["duration_ms"] = round(elapsed_ms, 2)
        return result


# ──────────────────────────────────────────────────────────────────────
# Registro Central de Herramientas
# ──────────────────────────────────────────────────────────────────────

class ToolRegistry:
    """Registro y ejecutor centralizado de herramientas autorizadas."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._execution_history: list[dict[str, Any]] = []

    def register(self, tool: BaseTool) -> None:
        """Registra una herramienta autorizada."""
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)

    def get(self, name: str) -> Optional[BaseTool]:
        """Obtiene una herramienta por nombre."""
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """Lista todas las herramientas con su esquema y descripción."""
        return [
            {
                "name":        t.name,
                "description": t.description,
                "is_safe":     t.is_safe,
                "parameters":  {
                    pname: {
                        "type":        p.type.__name__,
                        "required":    p.required,
                        "default":     p.default,
                        "description": p.description,
                    }
                    for pname, p in t.parameters.items()
                }
            }
            for t in self._tools.values()
        ]

    def execute_tool(self, name: str, context: dict[str, Any]) -> dict[str, Any]:
        """Busca y ejecuta de forma segura una herramienta autorizada."""
        tool = self.get(name)
        if not tool:
            return {
                "tool":      name,
                "success":   False,
                "error":     f"Herramienta '{name}' no registrada ni autorizada.",
                "output":    {},
            }

        res = tool.safe_execute(context)
        self._execution_history.append({
            "tool":      name,
            "timestamp": time.time(),
            "success":   res.get("success", False),
            "duration":  res.get("duration_ms", 0.0),
        })
        return res

    @property
    def execution_history(self) -> list[dict[str, Any]]:
        return list(self._execution_history)
