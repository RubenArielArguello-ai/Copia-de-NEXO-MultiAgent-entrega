"""
NEXO — Herramienta de Diagnóstico del Sistema.

Inspecciona de forma segura el estado del entorno del sistema operativo:
- Plataforma y arquitectura
- Espacio libre en disco
- Número de núcleos de CPU
- Carga media del sistema (load average)
- Estado de memoria Python

Herramienta 100% de lectura, sin red externa ni comandos destructivos.
"""

from __future__ import annotations
import os
import shutil
import platform
import subprocess
import re
import logging
from typing import Any

from nexo.tools.base_tool import BaseTool, ToolParameter, SecurityPolicy

logger = logging.getLogger(__name__)


class SystemDiagnosticTool(BaseTool):
    """
    Herramienta segura de diagnóstico de sistema y hardware básico.
    """

    @property
    def name(self) -> str:
        return "system_diagnostic"

    @property
    def description(self) -> str:
        return "Diagnóstico del sistema: espacio en disco, plataforma, CPU y carga del sistema"

    @property
    def parameters(self) -> dict[str, ToolParameter]:
        return {
            "path": ToolParameter(
                name="path",
                type=str,
                required=False,
                default="/",
                description="Ruta de disco a inspeccionar"
            )
        }

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        path = context.get("path", "/")

        # Espacio en disco
        try:
            total, used, free = shutil.disk_usage(path)
            disk_info = {
                "total_gb": round(total / (1024 ** 3), 2),
                "used_gb":  round(used / (1024 ** 3), 2),
                "free_gb":  round(free / (1024 ** 3), 2),
                "percent_used": round((used / total) * 100, 1),
            }
        except Exception as e:
            disk_info = {"error": str(e)}

        # Load average (en Unix/macOS)
        load_avg = None
        if hasattr(os, "getloadavg"):
            try:
                load_avg = [round(x, 2) for x in os.getloadavg()]
            except Exception:
                pass

        output = {
            "system": {
                "os": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "cpu_count": os.cpu_count() or 1,
            },
            "disk": disk_info,
            "memory": self._memory_info(),
            "processes": self._process_count(),
            "load_average_1_5_15m": load_avg,
            "python_version": platform.python_version(),
        }

        # Conclusión básica del estado
        is_disk_full = disk_info.get("percent_used", 0) > 95
        overall_status = "WARNING_DISK_FULL" if is_disk_full else "SYSTEM_HEALTHY"

        logger.info("[TOOL:system_diagnostic] Completed: %s", overall_status)

        return {
            "tool": self.name,
            "output": output,
            "overall_status": overall_status,
            "success": True,
        }

    @staticmethod
    def _memory_info() -> dict[str, Any]:
        """Read physical RAM counters where the OS exposes them without commands."""
        if platform.system() == "Darwin":
            try:
                total_run = SystemDiagnosticTool._readonly_command(["sysctl", "-n", "hw.memsize"])
                vm_run = SystemDiagnosticTool._readonly_command(["vm_stat"])
                if total_run.returncode == 0:
                    total = int(total_run.stdout.strip())
                    available = None
                    match = re.search(r"page size of (\d+) bytes", vm_run.stdout)
                    if match:
                        page = int(match.group(1))
                        free = sum(int(n) for n in re.findall(r"Pages (?:free|inactive|speculative|purgeable):\s+(\d+)\.", vm_run.stdout))
                        available = free * page
                    result = {"total_gb": round(total / 1024**3, 2)}
                    if available is not None:
                        result.update({"available_gb": round(available / 1024**3, 2),
                                       "used_percent": round((total-available)*100/total, 1)})
                    return result
            except (OSError, ValueError, subprocess.TimeoutExpired):
                pass
        if not hasattr(os, "sysconf"):
            return {"available": False}
        try:
            page = os.sysconf("SC_PAGE_SIZE")
            total = page * os.sysconf("SC_PHYS_PAGES")
            available_pages = os.sysconf("SC_AVPHYS_PAGES")
            available = page * available_pages
            return {"total_gb": round(total / 1024**3, 2),
                    "available_gb": round(available / 1024**3, 2),
                    "used_percent": round((total - available) * 100 / total, 1)}
        except (ValueError, OSError, AttributeError):
            return {"available": False}

    @staticmethod
    def _process_count() -> int | None:
        try:
            return sum(name.isdigit() for name in os.listdir("/proc"))
        except OSError:
            try:
                result = SystemDiagnosticTool._readonly_command(["ps", "-axo", "pid="])
                if result.returncode == 0:
                    return sum(bool(line.strip()) for line in result.stdout.splitlines())
            except (OSError, subprocess.TimeoutExpired):
                pass
            return None

    @staticmethod
    def _readonly_command(command: list[str]):
        allowed, reason = SecurityPolicy.validate_command(command)
        if not allowed:
            raise PermissionError(reason)
        return subprocess.run(command, capture_output=True, text=True, timeout=2)
