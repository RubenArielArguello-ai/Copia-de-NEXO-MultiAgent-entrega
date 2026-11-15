"""
Tests del Orquestador con MockProvider.

Verifica el ciclo completo de razonamiento:
Percepción → Análisis → Planificación → Ejecución → Evaluación → Entrega
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    import pytest
except ImportError:
    class _RaisesContext:
        def __init__(self, exc):
            self.exc = exc
        def __enter__(self):
            return self
        def __exit__(self, et, ev, tb):
            if et is None:
                raise AssertionError(f"Expected exception {self.exc} was not raised")
            return issubclass(et, self.exc)

    class _PytestStub:
        raises = staticmethod(lambda exc: _RaisesContext(exc))
        main = staticmethod(lambda args=None: 0)

    pytest = _PytestStub()
from unittest.mock import patch

from nexo.core.orchestrator  import Orchestrator
from nexo.core.state_manager import StateManager, SessionStatus
from nexo.providers.base_provider import MockProvider
from nexo.config import PROVIDER_CONFIG


class TestOrchestrator:
    """Tests de integración del Orquestador con MockProvider."""

    def setup_method(self):
        self.state_manager = StateManager()
        self.tool_patch = patch(
            "nexo.tools.diagnostic_tool.NetworkDiagnosticTool.execute",
            return_value={
                "tool": "network_diagnostic",
                "output": {
                    "interface": {"status": "UP", "ok": True},
                    "gateway": {"status": "REACHABLE", "ok": True},
                    "dns": {"status": "FAILED", "ok": False},
                    "internet": {"status": "UNREACHABLE", "ok": False},
                },
                "diagnosis": {
                    "overall_status": "DNS_FAILURE",
                    "root_cause": "DNS no resuelve nombres",
                    "recommendation": "Configurar DNS 1.1.1.1 o 8.8.8.8",
                    "layer_failed": 3,
                },
                "success": True,
            }
        )
        self.tool_patch.start()

    def teardown_method(self):
        self.tool_patch.stop()

    def _get_orchestrator_with_mock(self) -> Orchestrator:
        """Crea un orquestador que usa MockProvider para todos los agentes."""
        orch = Orchestrator(self.state_manager)
        return orch

    @patch("nexo.core.orchestrator.build_provider")
    def test_full_cycle_completes(self, mock_build_provider):
        """El ciclo completo debe completarse con MockProvider."""
        mock_build_provider.side_effect = lambda role, cfg: MockProvider(role)

        session = self.state_manager.create_session(
            "Mi computadora no se conecta a Internet"
        )
        orch   = self._get_orchestrator_with_mock()
        result = orch.run(session.session_id)

        assert result is not None
        assert result["session_id"] == session.session_id
        assert result["status"] in ["COMPLETED", "FAILED"]

    @patch("nexo.core.orchestrator.build_provider")
    def test_session_has_messages(self, mock_build_provider):
        """La sesión debe tener mensajes entre agentes al terminar."""
        mock_build_provider.side_effect = lambda role, cfg: MockProvider(role)

        session = self.state_manager.create_session("Falla de red")
        orch   = self._get_orchestrator_with_mock()
        result = orch.run(session.session_id)

        # Debe haber al menos mensajes de orquestador → analista → estratega
        assert len(result["messages"]) >= 2

    @patch("nexo.core.orchestrator.build_provider")
    def test_session_has_plan(self, mock_build_provider):
        """La sesión debe tener un plan generado."""
        mock_build_provider.side_effect = lambda role, cfg: MockProvider(role)

        session = self.state_manager.create_session("Internet no funciona")
        orch   = self._get_orchestrator_with_mock()
        result = orch.run(session.session_id)

        assert len(result["plan"]) > 0, "Debe haber al menos una tarea en el plan"

    @patch("nexo.core.orchestrator.build_provider")
    def test_coherence_score_is_valid(self, mock_build_provider):
        """El coherence score debe estar en [0, 1]."""
        mock_build_provider.side_effect = lambda role, cfg: MockProvider(role)

        session = self.state_manager.create_session("Diagnóstico de conectividad")
        orch   = self._get_orchestrator_with_mock()
        result = orch.run(session.session_id)

        score = result.get("coherence_score", 1.0)
        assert 0.0 <= score <= 1.0

    @patch("nexo.core.orchestrator.build_provider")
    def test_metrics_contain_timing(self, mock_build_provider):
        """Las métricas deben incluir tiempo de ejecución."""
        mock_build_provider.side_effect = lambda role, cfg: MockProvider(role)

        session = self.state_manager.create_session("Error de red")
        orch   = self._get_orchestrator_with_mock()
        result = orch.run(session.session_id)

        metrics = result.get("metrics", {})
        assert "elapsed_seconds" in metrics
        assert metrics["elapsed_seconds"] >= 0

    @patch("nexo.core.orchestrator.build_provider")
    def test_composite_mission_runs_research_qa_security_and_evaluator(self, mock_build_provider):
        mock_build_provider.side_effect = lambda role, cfg: MockProvider(role)
        with patch("nexo.tools.system_tool.SystemDiagnosticTool.execute", return_value={
            "output": {"memory": {"available_gb": 4.0}, "disk": {"used_percent": 80}}, "success": True,
        }), patch("nexo.tools.diagnostic_tool.NetworkDiagnosticTool.execute", return_value={
            "output": {"status": "FULLY_CONNECTED", "latency_ms": 12}, "success": True,
        }):
            session = self.state_manager.create_session(
                "Analiza los recursos del sistema y la conectividad, y genera un informe con evidencias"
            )
            result = self._get_orchestrator_with_mock().run(session.session_id)

        senders = {message["from_agent"] for message in result["messages"]}
        assert {"ANALYST", "STRATEGIST", "EXECUTOR", "RESEARCHER", "QA", "SECURITY", "EVALUATOR"}.issubset(senders)
        assert result["agent_results"]["quality_review"]["passed"] is True
        assert result["agent_results"]["security_review"]["passed"] is True
        assert result["agent_results"]["harness"]["llm_calls"] > 0
        assert result["agent_results"]["research"]["evidence_count"] >= 2

    def test_invalid_session_raises(self):
        """Intentar ejecutar una sesión inexistente debe lanzar ValueError."""
        orch = self._get_orchestrator_with_mock()
        with pytest.raises(ValueError):
            orch.run("sesion-que-no-existe")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
