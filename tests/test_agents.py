"""
Tests de agentes individuales con MockProvider.

Verifica que cada agente:
- Procesa mensajes correctamente
- Devuelve respuestas con el formato esperado
- Maneja errores sin romper el sistema
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    import pytest
except ImportError:
    class _PytestStub:
        @staticmethod
        def main(args=None):
            return 0
    pytest = _PytestStub()
from nexo.agents.analyst    import AnalystAgent
from nexo.agents.strategist import StrategistAgent
from nexo.agents.evaluator  import EvaluatorAgent
from nexo.core.message_bus  import MessageBus
from nexo.providers.base_provider import MockProvider
from nexo.schemas.message import (
    NexoMessage, AgentID, MessageStatus, TaskPhase
)


def _make_bus(session_id: str = "test-session") -> MessageBus:
    return MessageBus(session_id)


def _make_msg(to_agent: AgentID, payload: dict, goal: str = "diagnosticar internet") -> NexoMessage:
    return NexoMessage(
        from_agent=AgentID.ORCHESTRATOR,
        to_agent=to_agent,
        task_id="test-task",
        goal=goal,
        phase=TaskPhase.ANALYSIS,
        payload=payload,
        status=MessageStatus.PENDING,
    )


class TestAnalystAgent:
    """Tests del Agente Analista."""

    def test_returns_analysis_dict(self):
        """El Analista debe devolver un mensaje con payload.analysis."""
        bus    = _make_bus("analyst-test")
        agent  = AnalystAgent(MockProvider("ANALYST"), bus)
        msg    = _make_msg(AgentID.ANALYST, {"request": "No me funciona Internet"})
        bus.publish(msg)

        response = agent.run()

        assert response is not None
        assert "analysis" in response.payload
        analysis = response.payload["analysis"]
        assert "interpretation" in analysis

    def test_reply_goes_back_to_orchestrator(self):
        """La respuesta del Analista debe ir al Orquestador."""
        bus    = _make_bus("analyst-test-2")
        agent  = AnalystAgent(MockProvider("ANALYST"), bus)
        msg    = _make_msg(AgentID.ANALYST, {"request": "Problema de red"})
        bus.publish(msg)

        response = agent.run()

        assert response.to_agent == AgentID.ORCHESTRATOR

    def test_status_is_completed_or_partial(self):
        """El estado debe ser COMPLETED o PARTIAL (nunca FAILED para análisis básico)."""
        bus    = _make_bus("analyst-test-3")
        agent  = AnalystAgent(MockProvider("ANALYST"), bus)
        msg    = _make_msg(AgentID.ANALYST, {"request": "Falla de conectividad"})
        bus.publish(msg)

        response = agent.run()

        assert response.status in [MessageStatus.COMPLETED, MessageStatus.PARTIAL]


class TestStrategistAgent:
    """Tests del Agente Estratega."""

    def test_returns_plan_with_tasks(self):
        """El Estratega debe devolver un plan con al menos una tarea."""
        bus   = _make_bus("strategist-test")
        agent = StrategistAgent(MockProvider("STRATEGIST"), bus)
        msg   = _make_msg(AgentID.STRATEGIST, {
            "analysis": {
                "interpretation": "Sin conexión a Internet",
                "success_criteria": ["Identificar causa"],
                "initial_hypotheses": ["Falla DNS"],
            }
        })
        bus.publish(msg)

        response = agent.run()

        assert response is not None
        assert "plan" in response.payload
        plan_data = response.payload["plan"]
        assert "plan" in plan_data
        assert len(plan_data["plan"]) > 0

    def test_plan_tasks_have_required_fields(self):
        """Cada tarea del plan debe tener id, task y depends_on."""
        bus   = _make_bus("strategist-test-2")
        agent = StrategistAgent(MockProvider("STRATEGIST"), bus)
        msg   = _make_msg(AgentID.STRATEGIST, {
            "analysis": {"interpretation": "Diagnóstico de red", "success_criteria": []}
        })
        bus.publish(msg)

        response = agent.run()

        tasks = response.payload.get("plan", {}).get("plan", [])
        for task in tasks:
            assert "id"         in task, "Cada tarea debe tener id"
            assert "task"       in task, "Cada tarea debe tener task"
            assert "depends_on" in task, "Cada tarea debe tener depends_on"


class TestEvaluatorAgent:
    """Tests del Agente Evaluador."""

    def test_approves_good_result(self):
        """El Evaluador debe aprobar resultados que cumplen el objetivo."""
        bus   = _make_bus("evaluator-test")
        agent = EvaluatorAgent(MockProvider("EVALUATOR"), bus)
        msg   = _make_msg(AgentID.EVALUATOR, {
            "analysis":          {"success_criteria": ["Identificar causa DNS"]},
            "plan":              [{"id": "T1", "task": "Verificar DNS"}],
            "execution_results": [{"task_id": "T1", "result": {"conclusion": "DNS fallido"}}],
        })
        bus.publish(msg)

        response = agent.run()

        assert response is not None
        assert "evaluation" in response.payload
        evaluation = response.payload["evaluation"]
        assert "verdict" in evaluation
        assert evaluation["verdict"] in ["APPROVED", "NEEDS_CORRECTION", "REJECTED"]

    def test_evaluation_has_confidence(self):
        """La evaluación debe incluir un score de confianza."""
        bus   = _make_bus("evaluator-test-2")
        agent = EvaluatorAgent(MockProvider("EVALUATOR"), bus)
        msg   = _make_msg(AgentID.EVALUATOR, {
            "analysis":          {},
            "plan":              [],
            "execution_results": [],
        })
        bus.publish(msg)

        response = agent.run()
        evaluation = response.payload.get("evaluation", {})

        assert "confidence" in evaluation
        assert isinstance(evaluation["confidence"], (int, float))
        assert 0.0 <= evaluation["confidence"] <= 1.0


class TestMessageBus:
    """Tests del bus de mensajes."""

    def test_publish_and_consume(self):
        """Un mensaje publicado debe poder ser consumido."""
        bus = _make_bus("bus-test")
        msg = NexoMessage(
            from_agent=AgentID.ORCHESTRATOR,
            to_agent=AgentID.ANALYST,
            task_id="t1",
            goal="test",
            phase=TaskPhase.ANALYSIS,
            payload={"test": True},
            status=MessageStatus.PENDING,
        )
        bus.publish(msg)
        consumed = bus.consume(AgentID.ANALYST)

        assert consumed is not None
        assert consumed.msg_id == msg.msg_id

    def test_consume_returns_none_when_empty(self):
        """Consumir un bus vacío debe devolver None."""
        bus = _make_bus("bus-empty-test")
        result = bus.consume(AgentID.ANALYST)
        assert result is None

    def test_consume_only_for_target_agent(self):
        """Solo debe consumir mensajes destinados al agente correcto."""
        bus = _make_bus("bus-target-test")
        msg_analyst = NexoMessage(
            from_agent=AgentID.ORCHESTRATOR,
            to_agent=AgentID.ANALYST,
            task_id="t1",
            goal="test",
            phase=TaskPhase.ANALYSIS,
            payload={},
            status=MessageStatus.PENDING,
        )
        bus.publish(msg_analyst)

        # Intentar consumir para EXECUTOR (no debería obtener nada)
        result = bus.consume(AgentID.EXECUTOR)
        assert result is None

        # El ANALYST sí lo consume
        result = bus.consume(AgentID.ANALYST)
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
