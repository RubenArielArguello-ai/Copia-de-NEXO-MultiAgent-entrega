"""
Tests del NEXO-Coherence Monitor (NCM).

Verifica las 5 capacidades de detección de anomalías
usando casos sintéticos sin necesidad de Ollama.
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
from nexo.tools.coherence_monitor import CoherenceMonitor, CoherenceFlag
from nexo.schemas.message import (
    NexoMessage, AgentID, MessageStatus, TaskPhase
)
from nexo.core.state_manager import SubTask


def _make_msg(from_agent: str, to_agent: str, payload: dict, goal: str = "diagnosticar red") -> NexoMessage:
    return NexoMessage(
        from_agent=AgentID(from_agent),
        to_agent=AgentID(to_agent),
        task_id="test-session",
        goal=goal,
        phase=TaskPhase.ANALYSIS,
        payload=payload,
        status=MessageStatus.COMPLETED,
    )


class TestCoherenceMonitor:
    """Suite de tests para el NCM."""

    def setup_method(self):
        self.ncm = CoherenceMonitor()

    # ── Test 1: Sin anomalías ──────────────────────────────────────
    def test_no_anomalies_perfect_score(self):
        """Un sistema coherente debe tener score cercano a 1.0."""
        messages = [
            _make_msg("ORCHESTRATOR", "ANALYST",    {"request": "diagnosticar internet red conexión"}, "diagnosticar internet"),
            _make_msg("ANALYST",      "ORCHESTRATOR", {"analysis": {"interpretation": "diagnóstico internet red"}}, "diagnosticar internet"),
        ]
        plan = [{"id": "T1", "task": "verificar interfaz red", "depends_on": []}]

        report = self.ncm.analyze(
            session_id="test",
            messages=messages,
            plan=plan,
            goal="diagnosticar internet",
        )

        assert report.score >= 0.7, f"Score esperado ≥ 0.7, obtenido: {report.score}"
        flags = {a.flag for a in report.anomalies}
        assert CoherenceFlag.CONTRADICTION not in flags
        assert CoherenceFlag.MISSING_DEPENDENCY not in flags

    # ── Test 2: Detección de duplicación de tareas ─────────────────
    def test_detects_task_duplication(self):
        """Debe detectar cuando dos tareas son semánticamente iguales."""
        plan = [
            {"id": "T1", "task": "verificar resolución DNS del sistema", "depends_on": []},
            {"id": "T2", "task": "comprobar resolución DNS del sistema", "depends_on": []},
            {"id": "T3", "task": "hacer ping al gateway de red",          "depends_on": []},
        ]

        report = self.ncm.analyze(
            session_id="test",
            messages=[],
            plan=plan,
            goal="diagnosticar internet",
        )

        flags = {a.flag for a in report.anomalies}
        assert CoherenceFlag.TASK_DUPLICATION in flags, \
            "Debería detectar duplicación entre T1 y T2"
        assert report.score < 1.0

    # ── Test 3: Detección de contradicción ────────────────────────
    def test_detects_contradiction(self):
        """Debe detectar cuando dos agentes afirman cosas opuestas."""
        messages = [
            _make_msg("ANALYST",  "ORCHESTRATOR", {"data": "la interfaz de red está up y activa"}),
            _make_msg("EXECUTOR", "ORCHESTRATOR", {"data": "la interfaz de red está down inactiva"}),
        ]

        report = self.ncm.analyze(
            session_id="test",
            messages=messages,
            plan=[],
            goal="diagnosticar internet",
        )

        flags = {a.flag for a in report.anomalies}
        assert CoherenceFlag.CONTRADICTION in flags, \
            "Debería detectar contradicción up/down"

    # ── Test 4: Dependencia incumplida ────────────────────────────
    def test_detects_missing_dependency(self):
        """Debe detectar cuando una tarea depende de una tarea inexistente."""
        plan = [
            {"id": "T1", "task": "verificar interfaz",  "depends_on": []},
            {"id": "T2", "task": "verificar DNS",        "depends_on": ["T1", "T_PHANTOM"]},
        ]

        report = self.ncm.analyze(
            session_id="test",
            messages=[],
            plan=plan,
            goal="diagnosticar internet",
        )

        flags = {a.flag for a in report.anomalies}
        assert CoherenceFlag.MISSING_DEPENDENCY in flags, \
            "Debería detectar que T_PHANTOM no existe"
        assert any(a.severity == "critical" for a in report.anomalies)

    # ── Test 5: Riesgo de ciclo infinito ──────────────────────────
    def test_detects_cycle_risk(self):
        """Debe detectar riesgo de ciclo cuando la iteración es alta."""
        report = self.ncm.analyze(
            session_id="test",
            messages=[],
            plan=[],
            goal="diagnosticar internet",
            iteration=5,  # >= MAX_ITERATIONS_WARNING
        )

        assert report.cycle_risk is True
        assert report.should_replan is True
        assert report.score < 1.0

    # ── Test 6: Score disminuye con anomalías ─────────────────────
    def test_score_decreases_with_anomalies(self):
        """El score debe ser menor cuando hay más anomalías."""
        # Plan sin anomalías
        clean_plan = [{"id": "T1", "task": "diagnosticar conexión", "depends_on": []}]
        report_clean = self.ncm.analyze("test", [], clean_plan, "diagnosticar internet")

        # Plan con duplicación + dependencia inválida
        dirty_plan = [
            {"id": "T1", "task": "verificar conexión internet red",    "depends_on": ["T_X"]},
            {"id": "T2", "task": "comprobar internet conexión red",    "depends_on": []},
        ]
        report_dirty = self.ncm.analyze("test", [], dirty_plan, "diagnosticar internet")

        assert report_clean.score > report_dirty.score, \
            f"Clean ({report_clean.score}) debe ser > Dirty ({report_dirty.score})"

    # ── Test 7: Recomendación no vacía cuando hay anomalías ───────
    def test_recommendation_not_empty_when_anomalies(self):
        """Debe generar una recomendación cuando hay anomalías."""
        plan = [
            {"id": "T1", "task": "verificar DNS red",    "depends_on": ["T_X"]},
            {"id": "T2", "task": "comprobar DNS red",    "depends_on": []},
        ]
        report = self.ncm.analyze("test", [], plan, "diagnosticar internet")

        assert report.recommendation, "Debe haber una recomendación"
        assert report.recommendation != "Colaboración coherente. No se requieren acciones."

    # ── Test 8: execute() devuelve formato correcto ───────────────
    def test_execute_returns_correct_format(self):
        """La interfaz BaseTool.execute() debe devolver dict con 'tool' y 'output'."""
        context = {
            "session_id": "test",
            "messages":   [],
            "plan":       [],
            "goal":       "diagnosticar internet",
            "iteration":  0,
        }
        result = self.ncm.execute(context)

        assert result["tool"]    == "coherence_monitor"
        assert result["success"] is True
        assert "output" in result
        assert "coherence_score" in result["output"]
        assert 0.0 <= result["output"]["coherence_score"] <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
