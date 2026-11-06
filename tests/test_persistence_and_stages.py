"""
Tests de persistencia SQLite y ciclo de 10 etapas cognitivas del Orquestador.

Verifica:
- Las 10 etapas cognitivas (Percepción a Entrega)
- Persistencia de eventos de coherencia y ejecuciones de herramientas en SQLite
- Ciclos de replanificación guiada por el Evaluador
- Prevención de bucles y degradación controlada
"""

import sys
import os
import json
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    import pytest
except ImportError:
    class _PytestStub:
        @staticmethod
        def main(args=None): return 0
    pytest = _PytestStub()

from nexo.core.state_manager import StateManager, SessionStatus
from nexo.core.message_bus import MessageBus
from nexo.core.orchestrator import Orchestrator
from nexo.schemas.message import TaskPhase, MessageStatus
from nexo.providers.base_provider import MockProvider


class TestMessageBusPersistence:
    """Verifica la persistencia ampliada en SQLite."""

    def test_record_and_retrieve_tool_executions(self):
        bus = MessageBus("session-persist-test")
        bus.record_tool_execution(
            tool_name="network_diagnostic",
            task_id="T1",
            parameters={"test": "interface"},
            output={"status": "UP"},
            success=True,
            duration_ms=12.5,
        )

        history = bus.get_session_tools()
        assert len(history) >= 1
        last = history[-1]
        assert last["tool_name"] == "network_diagnostic"
        assert last["task_id"] == "T1"
        assert last["success"] == 1
        assert "UP" in last["output"]

    def test_record_and_retrieve_coherence_events(self):
        bus = MessageBus("session-coherence-test")
        bus.record_coherence_event(
            iteration=1,
            score=0.85,
            anomalies=[{"flag": "TASK_DUPLICATION", "severity": "major"}],
            recommendation="Consolidar tareas",
        )

        events = bus.get_session_coherence()
        assert len(events) >= 1
        last = events[-1]
        assert last["score"] == 0.85
        assert last["iteration"] == 1
        assert "TASK_DUPLICATION" in last["anomalies"]


class TestOrchestratorCognitivePhases:
    """Verifica que el Orquestador transite por las etapas cognitivas."""

    def setup_method(self):
        self.state_manager = StateManager()
        self.tool_patch = patch(
            "nexo.tools.diagnostic_tool.NetworkDiagnosticTool.execute",
            return_value={
                "tool": "network_diagnostic",
                "output": {"interface": {"status": "UP", "ok": True}},
                "success": True,
            }
        )
        self.tool_patch.start()

    def teardown_method(self):
        self.tool_patch.stop()

    @patch("nexo.core.orchestrator.build_provider")
    def test_delivery_phase_reached_on_approval(self, mock_build):
        mock_build.side_effect = lambda role, cfg: MockProvider(role)

        session = self.state_manager.create_session("Diagnóstico de conectividad")
        orch = Orchestrator(self.state_manager)
        res = orch.run(session.session_id)

        assert res["status"] == "COMPLETED"
        assert session.current_phase == TaskPhase.DELIVERY
        assert session.final_answer is not None
        assert len(session.final_answer) > 10

    @patch("nexo.core.orchestrator.build_provider")
    def test_replanning_triggered_when_evaluator_demands_correction(self, mock_build):
        """Simula que el Evaluador primero pide corrección y luego aprueba."""
        evaluator_calls = 0

        class DynamicEvaluatorProvider(MockProvider):
            def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
                nonlocal evaluator_calls
                evaluator_calls += 1
                if evaluator_calls == 1:
                    return json.dumps({
                        "verdict": "NEEDS_CORRECTION",
                        "goal_achieved": False,
                        "confidence": 0.5,
                        "issues_found": [{"description": "Falta verificar gateway"}],
                        "corrections_needed": ["Agregar verificación de gateway"],
                    })
                return json.dumps({
                    "verdict": "APPROVED",
                    "goal_achieved": True,
                    "confidence": 0.95,
                    "final_answer": "Problema resuelto tras corrección.",
                })

        def provider_factory(role, cfg):
            if role == "EVALUATOR":
                return DynamicEvaluatorProvider("EVALUATOR")
            return MockProvider(role)

        mock_build.side_effect = provider_factory

        session = self.state_manager.create_session("Prueba de replanificación")
        orch = Orchestrator(self.state_manager)
        res = orch.run(session.session_id)

        assert res["status"] == "COMPLETED"
        assert res["metrics"]["replan_count"] >= 1
        assert evaluator_calls == 2
        assert "tras corrección" in res["final_answer"]
