"""
NEXO — Herramienta de Diagnóstico de Red.

Realiza pruebas reales de conectividad usando comandos del sistema operativo:
  - Verificación de interfaz de red activa
  - Ping al gateway
  - Resolución DNS
  - Ping a DNS público (8.8.8.8)

Esta es una herramienta REAL que ejecuta comandos reales.
Los resultados reflejan el estado actual del sistema donde se ejecuta NEXO.
"""

from __future__ import annotations
import platform
import subprocess
import socket
import logging
from typing import Any

from nexo.tools.base_tool import BaseTool, ToolParameter, SecurityPolicy

logger = logging.getLogger(__name__)


def _run_cmd(cmd: list[str], timeout: int = 5) -> tuple[bool, str]:
    """Ejecuta un comando de sistema validado contra la política de seguridad y devuelve (éxito, output)."""
    is_safe, error_msg = SecurityPolicy.validate_command(cmd)
    if not is_safe:
        logger.error("[SECURITY] Command rejected by policy: %s (Reason: %s)", cmd, error_msg)
        return False, f"Rechazado por seguridad: {error_msg}"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, f"Timeout después de {timeout}s"
    except FileNotFoundError:
        return False, f"Comando no encontrado: {cmd[0]}"
    except Exception as e:
        return False, str(e)


class NetworkDiagnosticTool(BaseTool):
    """
    Herramienta de diagnóstico de red de NEXO.

    Ejecuta pruebas reales en capas:
      Layer 1: Interfaz de red
      Layer 2: Gateway (ARP/ping)
      Layer 3: DNS
      Layer 4: Internet (ping a 8.8.8.8)
    """

    @property
    def parameters(self) -> dict[str, ToolParameter]:
        return {
            "session_id": ToolParameter(name="session_id", type=str, required=False, default="", description="ID de la sesión"),
            "host_dns":   ToolParameter(name="host_dns", type=str, required=False, default="google.com", description="Host para prueba DNS específica"),
        }

    @property
    def name(self) -> str:
        return "network_diagnostic"

    @property
    def description(self) -> str:
        return "Diagnóstico completo de red: interfaz, gateway, DNS e Internet"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Ejecuta el diagnóstico completo de red.
        """
        os_name = platform.system()
        results = {}

        # ── Layer 1: Interfaz de red ──────────────────────────────────
        results["interface"] = self._check_interface(os_name)

        # ── Layer 2: Gateway ─────────────────────────────────────────
        results["gateway"] = self._check_gateway(os_name)

        # ── Layer 3: DNS ─────────────────────────────────────────────
        results["dns"] = self._check_dns()

        # ── Layer 4: Internet ─────────────────────────────────────────
        results["internet"] = self._check_internet(os_name)

        # Diagnóstico consolidado
        diagnosis = self._consolidate(results)

        logger.info("Network diagnostic completed: %s", diagnosis["overall_status"])

        return {
            "tool":      self.name,
            "output":    results,
            "diagnosis": diagnosis,
            "success":   True,
        }

    # ──────────────────────────────────────────────────────────────────
    # Métodos internos por capa
    # ──────────────────────────────────────────────────────────────────

    def _check_interface(self, os_name: str) -> dict:
        """Verifica si hay interfaces de red activas."""
        if os_name == "Darwin":   # macOS
            ok, out = _run_cmd(["ifconfig"])
        elif os_name == "Windows":
            ok, out = _run_cmd(["ipconfig"])
        else:                      # Linux
            ok, out = _run_cmd(["ip", "addr"])

        # Detectar interfaces activas (simplificado)
        active = ok and ("RUNNING" in out or "UP" in out or "IPv4" in out or
                         "inet " in out or "Autoconfiguration" in out)
        return {
            "status":  "UP" if active else "DOWN",
            "details": out[:500] if ok else out,
            "ok":      active,
        }

    def _check_gateway(self, os_name: str) -> dict:
        """Intenta hacer ping al gateway de red."""
        # Detectar gateway
        gateway = None
        if os_name == "Darwin":
            ok, out = _run_cmd(["netstat", "-rn"])
            for line in out.splitlines():
                if "default" in line or "0.0.0.0" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        candidate = parts[1]
                        if self._is_ip(candidate):
                            gateway = candidate
                            break
        elif os_name == "Windows":
            ok, out = _run_cmd(["ipconfig"])
            for line in out.splitlines():
                if "Gateway" in line and ":" in line:
                    candidate = line.split(":")[-1].strip()
                    if self._is_ip(candidate):
                        gateway = candidate
                        break
        else:  # Linux
            ok, out = _run_cmd(["ip", "route"])
            for line in out.splitlines():
                if line.startswith("default"):
                    parts = line.split()
                    if "via" in parts:
                        gateway = parts[parts.index("via") + 1]
                        break

        if not gateway:
            return {"status": "UNKNOWN", "gateway": None, "ok": False,
                    "details": "No se pudo detectar el gateway"}

        # Ping al gateway
        ping_cmd = (
            ["ping", "-c", "3", "-W", "2", gateway] if os_name != "Windows"
            else ["ping", "-n", "3", "-w", "2000", gateway]
        )
        ok, out = _run_cmd(ping_cmd)
        return {
            "status":  "REACHABLE" if ok else "UNREACHABLE",
            "gateway": gateway,
            "ok":      ok,
            "details": out[:300],
        }

    def _check_dns(self) -> dict:
        """Verifica la resolución DNS."""
        test_hosts = ["google.com", "cloudflare.com", "example.com"]
        resolved   = []
        failed     = []

        for host in test_hosts:
            try:
                ip = socket.gethostbyname(host)
                resolved.append({"host": host, "ip": ip})
            except socket.gaierror as e:
                failed.append({"host": host, "error": str(e)})

        ok = len(resolved) > 0
        return {
            "status":   "WORKING" if ok else "FAILED",
            "ok":       ok,
            "resolved": resolved,
            "failed":   failed,
            "details":  f"Resueltos: {len(resolved)}/{len(test_hosts)}",
        }

    def _check_internet(self, os_name: str) -> dict:
        """Ping a DNS públicos para verificar conectividad a Internet."""
        targets = ["8.8.8.8", "1.1.1.1"]
        reachable = []

        for target in targets:
            if os_name == "Windows":
                ok, out = _run_cmd(["ping", "-n", "2", "-w", "2000", target])
            else:
                ok, out = _run_cmd(["ping", "-c", "2", "-W", "2", target])
            if ok:
                reachable.append(target)

        ok = len(reachable) > 0
        return {
            "status":    "REACHABLE" if ok else "UNREACHABLE",
            "ok":        ok,
            "reachable": reachable,
            "details":   f"Accesibles: {reachable}",
        }

    def _consolidate(self, results: dict) -> dict:
        """
        Genera un diagnóstico consolidado y una recomendación.
        """
        interface = results["interface"]["ok"]
        gateway   = results["gateway"]["ok"]
        dns       = results["dns"]["ok"]
        internet  = results["internet"]["ok"]

        if not interface:
            return {
                "overall_status":  "NO_INTERFACE",
                "root_cause":      "Ninguna interfaz de red activa detectada",
                "recommendation":  "Verificar que WiFi o Ethernet estén habilitados. Revisar drivers de red.",
                "layer_failed":    1,
            }
        if not gateway:
            return {
                "overall_status":  "NO_GATEWAY",
                "root_cause":      "Interfaz activa pero sin alcance al gateway",
                "recommendation":  "Verificar cable/WiFi, reiniciar router. Verificar asignación DHCP.",
                "layer_failed":    2,
            }
        if not dns:
            return {
                "overall_status":  "DNS_FAILURE",
                "root_cause":      "Gateway accesible pero DNS no resuelve nombres",
                "recommendation":  "Cambiar DNS a 1.1.1.1 (Cloudflare) o 8.8.8.8 (Google) manualmente.",
                "layer_failed":    3,
            }
        if not internet:
            return {
                "overall_status":  "INTERNET_UNREACHABLE",
                "root_cause":      "DNS funciona pero no hay alcance a Internet",
                "recommendation":  "Posible bloqueo de firewall o ISP. Contactar al proveedor.",
                "layer_failed":    4,
            }

        return {
            "overall_status":  "FULLY_CONNECTED",
            "root_cause":      "Todas las capas de red funcionan correctamente",
            "recommendation":  "La conectividad de red es normal. El problema puede estar en la aplicación.",
            "layer_failed":    None,
        }

    @staticmethod
    def _is_ip(s: str) -> bool:
        """Verifica si un string es una IP válida."""
        parts = s.split(".")
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            return False
