"""
Tests de seguridad y sistema de herramientas de NEXO.

Verifica:
- Prevención de inyección de comandos en SecurityPolicy
- Validación de parámetros de herramientas
- Ejecución segura con safe_execute y captura de excepciones
- Herramientas: NetworkDiagnosticTool, SystemDiagnosticTool, PortCheckTool
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    import pytest
except ImportError:
    class _PytestStub:
        @staticmethod
        def main(args=None): return 0
    pytest = _PytestStub()

from nexo.tools.base_tool import (
    SecurityPolicy, ToolParameter, BaseTool, ToolRegistry
)
from nexo.tools.system_tool import SystemDiagnosticTool
from nexo.tools.port_tool import PortCheckTool
from nexo.tools.diagnostic_tool import NetworkDiagnosticTool


class TestSecurityPolicy:
    """Verifica que la política de seguridad impida comandos y parámetros peligrosos."""

    def test_blocks_dangerous_characters(self):
        """Metacaracteres de inyección de shell deben ser rechazados."""
        dangerous_inputs = [
            "google.com; rm -rf /",
            "8.8.8.8 | cat /etc/passwd",
            "`whoami`",
            "$(id)",
            "host && reboot",
            "test\nls -la",
        ]
        for payload in dangerous_inputs:
            assert not SecurityPolicy.is_safe_string(payload), f"Debería bloquear: {payload}"

    def test_allows_safe_strings(self):
        """Strings alfanuméricos y nombres de host deben ser admitidos."""
        safe_inputs = ["google.com", "8.8.8.8", "192.168.1.1", "eth0", "en0", "diagnóstico"]
        for s in safe_inputs:
            assert SecurityPolicy.is_safe_string(s), f"Debería permitir: {s}"

    def test_rejects_disallowed_binaries(self):
        """Comandos destructivos deben ser bloqueados de inmediato."""
        disallowed = [["rm", "-rf", "/tmp"], ["sudo", "reboot"], ["sh", "-c", "ls"], ["kill", "1234"]]
        for cmd in disallowed:
            ok, err = SecurityPolicy.validate_command(cmd)
            assert not ok
            assert "prohibido" in err or "no pertenece" in err

    def test_allows_authorized_system_commands(self):
        """Comandos de diagnóstico autorizados deben ser aceptados."""
        allowed = [["ifconfig"], ["ping", "-c", "1", "8.8.8.8"], ["netstat", "-rn"], ["uname", "-a"]]
        for cmd in allowed:
            ok, err = SecurityPolicy.validate_command(cmd)
            assert ok, f"Comando válido rechazado: {cmd} ({err})"


class TestToolParameters:
    """Verifica la validación de esquemas de parámetros."""

    def test_parameter_type_validation(self):
        param = ToolParameter(name="port", type=int, required=True)
        ok, _ = param.validate(80)
        assert ok
        ok_bad, err = param.validate("80")
        assert not ok_bad
        assert "debe ser de tipo int" in err

    def test_parameter_required_validation(self):
        param = ToolParameter(name="host", type=str, required=True)
        ok, err = param.validate(None)
        assert not ok
        assert "obligatorio" in err

    def test_parameter_allowed_values(self):
        param = ToolParameter(name="mode", type=str, allowed_values=["fast", "deep"])
        ok, _ = param.validate("fast")
        assert ok
        ok_bad, _ = param.validate("ultra")
        assert not ok_bad


class TestSystemDiagnosticTool:
    """Verifica la herramienta de diagnóstico de sistema."""

    def test_executes_safely_and_returns_hardware_info(self):
        tool = SystemDiagnosticTool()
        result = tool.safe_execute({"path": "/"})
        assert result["success"] is True
        assert result["tool"] == "system_diagnostic"
        output = result["output"]
        assert "disk" in output
        assert "system" in output
        assert "cpu_count" in output["system"]
        assert output["system"]["cpu_count"] >= 1
        assert "total_gb" in output["disk"]


class TestPortCheckTool:
    """Verifica la herramienta de verificación de puertos."""

    def test_rejects_invalid_port(self):
        tool = PortCheckTool()
        result = tool.safe_execute({"host": "localhost", "port": 999999})
        assert result["success"] is False
        assert "inválido" in result["error"].lower()

    def test_validates_required_parameters(self):
        tool = PortCheckTool()
        result = tool.safe_execute({})
        assert result["success"] is False
        assert "requerido" in result["error"].lower() or "obligatorio" in result["error"].lower()


class TestToolRegistry:
    """Verifica el registro central y ejecución de herramientas."""

    def test_register_and_list_tools(self):
        reg = ToolRegistry()
        reg.register(SystemDiagnosticTool())
        reg.register(PortCheckTool())
        tools = reg.list_tools()
        names = [t["name"] for t in tools]
        assert "system_diagnostic" in names
        assert "port_check" in names

    def test_execute_unregistered_tool_returns_error(self):
        reg = ToolRegistry()
        res = reg.execute_tool("herramienta_fantasma", {})
        assert res["success"] is False
        assert "no registrada" in res["error"]
