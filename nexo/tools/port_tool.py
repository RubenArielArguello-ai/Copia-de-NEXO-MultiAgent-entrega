"""
NEXO — Herramienta de Verificación de Puertos de Red.

Comprueba si un puerto TCP en un host determinado está accesible
usando sockets seguros con timeout no bloqueante.
"""

from __future__ import annotations
import socket
import logging
from typing import Any

from nexo.tools.base_tool import BaseTool, ToolParameter, SecurityPolicy

logger = logging.getLogger(__name__)


class PortCheckTool(BaseTool):
    """
    Herramienta segura de verificación de puertos TCP.
    """

    @property
    def name(self) -> str:
        return "port_check"

    @property
    def description(self) -> str:
        return "Verifica si un puerto TCP está abierto y accesible en un host determinado"

    @property
    def parameters(self) -> dict[str, ToolParameter]:
        return {
            "host": ToolParameter(
                name="host",
                type=str,
                required=True,
                description="Nombre de host o dirección IP a comprobar"
            ),
            "port": ToolParameter(
                name="port",
                type=int,
                required=True,
                description="Número de puerto TCP (1-65535)"
            ),
            "timeout": ToolParameter(
                name="timeout",
                type=int,
                required=False,
                default=3,
                description="Timeout en segundos para la conexión"
            )
        }

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        host = context.get("host", "").strip()
        port = context.get("port")
        timeout = min(10, max(1, int(context.get("timeout", 3))))

        if not host:
            return {"tool": self.name, "success": False, "error": "El parámetro 'host' es requerido."}

        if not isinstance(port, int) or port < 1 or port > 65535:
            return {"tool": self.name, "success": False, "error": f"Puerto inválido: {port}. Debe estar entre 1 y 65535."}

        if not SecurityPolicy.is_safe_string(host):
            return {"tool": self.name, "success": False, "error": f"Host '{host}' contiene caracteres inválidos."}

        is_open = False
        error_reason = None

        try:
            with socket.create_connection((host, port), timeout=timeout):
                is_open = True
        except (socket.timeout, TimeoutError):
            error_reason = f"Timeout tras {timeout}s esperando respuesta"
        except ConnectionRefusedError:
            error_reason = "Conexión rechazada por el host"
        except socket.gaierror as e:
            error_reason = f"No se pudo resolver el host '{host}': {e}"
        except OSError as e:
            error_reason = str(e)

        logger.info("[TOOL:port_check] %s:%d -> %s", host, port, "OPEN" if is_open else f"CLOSED ({error_reason})")

        return {
            "tool": self.name,
            "output": {
                "host": host,
                "port": port,
                "status": "OPEN" if is_open else "CLOSED",
                "is_open": is_open,
                "details": "Conexión TCP establecida exitosamente" if is_open else error_reason,
            },
            "success": True,
        }
