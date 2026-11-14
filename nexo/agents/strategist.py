"""
NEXO — Agente Estratega.

Skill: Planificación y descomposición de problemas.

Responsabilidades:
  - Diseñar un plan de resolución basado en el análisis
  - Dividir el problema en subtareas con dependencias
  - Asignar cada subtarea al agente correcto
  - Revisar el plan cuando aparecen nuevos resultados
"""

from __future__ import annotations
import json
import re

from nexo.agents.base_agent import BaseAgent
from nexo.schemas.message import (
    AgentID, MessageStatus, NexoMessage, TaskPhase
)


class StrategistAgent(BaseAgent):
    """
    Agente Estratega de NEXO.

    Recibe el análisis del Analista y produce un plan de acción
    con subtareas, dependencias y asignaciones.
    """

    agent_id = AgentID.STRATEGIST

    @property
    def system_prompt(self) -> str:
        return """Eres el Agente Estratega del sistema NEXO.

Tu rol es PLANIFICAR la resolución de problemas técnicos.

Dado un análisis de problema, produce un plan de acción en JSON:

{
  "strategy": "descripción de la estrategia general",
  "approach": "top-down|bottom-up|diagnostic-layers|investigative",
  "plan": [
    {
      "id": "T1",
      "task": "descripción concreta de la tarea",
      "agent": "EXECUTOR",
      "depends_on": [],
      "expected_output": "qué debe devolver esta tarea",
      "priority": 1
    }
  ],
  "risk_assessment": "descripción de riesgos del plan",
  "success_condition": "cómo saber que el plan se completó",
  "max_steps": 3
}

REGLAS:
- Cada tarea debe ser ATÓMICA (una sola responsabilidad).
- Las dependencias deben ser correctas: T2 no puede depender de T3 si T3 no existe aún.
- Asigna tareas de diagnóstico técnico siempre a EXECUTOR.
- Asigna tareas de verificación a EVALUATOR.
- Mantén el plan MINIMALISTA: máximo 3 tareas, incluso para solicitudes simples.
- Crea tareas solo para acciones técnicas realmente ejecutables. Si una sola herramienta
  resuelve la solicitud, crea una única tarea para esa herramienta.
- No conviertas criterios, limitaciones, hipótesis, prioridad, complejidad, resumen ni
  evaluación en tareas; esos datos pertenecen al análisis o al Evaluador.
- No asignes al Ejecutor tareas que solo pidan redactar, resumir o enumerar información.
- No dividas una única acción de diagnóstico en subtareas de reporte.
- Responde SIEMPRE en JSON válido."""

    def process(self, msg: NexoMessage) -> NexoMessage:
        """
        Genera un plan de resolución basado en el análisis del Analista.
        """
        analysis = msg.payload.get("analysis", {})
        self._log.info(
            "Planning for category: %s",
            analysis.get("category", "unknown")
        )

        user_prompt = f"""Análisis del problema:
---
{json.dumps(analysis, ensure_ascii=False, indent=2)}
---

Objetivo global: {msg.goal}
Criterios de éxito: {analysis.get("success_criteria", [])}
Hipótesis: {analysis.get("initial_hypotheses", [])}

Genera el plan de acción. Prioriza acciones concretas que usen una herramienta disponible.
La evaluación y el resumen final los hará el Evaluador después de ejecutar el plan; no los
incluyas como subtareas."""

        # Un modelo puede devolver JSON sintácticamente válido pero sin un plan,
        # o fallar durante la inferencia. La misión conserva una ruta de
        # recuperación determinista basada exclusivamente en el objetivo dado.
        try:
            plan = self.call_llm_json(user_prompt)
        except Exception as exc:
            self._log.warning("Strategist inference failed; building a constrained plan: %s", exc)
            plan = {"parse_error": True, "fallback_reason": str(exc)}

        tasks = plan.get("plan", [])
        if not isinstance(tasks, list):
            tasks = []
        tasks = [task for task in tasks if isinstance(task, dict) and task.get("task")]
        if not tasks or plan.get("parse_error"):
            goal = str(msg.goal or analysis.get("interpretation", "")).strip()
            # El orquestador valida nuevamente que la tarea corresponda a una
            # herramienta disponible. El fallback nunca afirma haber ejecutado.
            tasks = [{
                "id": "T1", "task": goal, "agent": "EXECUTOR", "depends_on": [],
                "expected_output": "Evidencia observada por una herramienta autorizada", "priority": 1,
            }] if goal else []
            plan = {
                "strategy": "Plan mínimo recuperado desde el objetivo original",
                "approach": "investigative", "plan": tasks,
                "risk_assessment": "El plan debe coincidir con una herramienta disponible",
                "success_condition": "La herramienta produce evidencia verificable",
                "max_steps": 1, "fallback_used": True,
                "fallback_reason": plan.get("fallback_reason", "respuesta sin tareas ejecutables"),
            }

        is_valid = bool(tasks)

        evidence = [
            f"Estrategia: {plan.get('strategy', 'no especificada')}",
            f"Tareas generadas: {len(tasks)}",
            f"Riesgo identificado: {plan.get('risk_assessment', 'no evaluado')}",
        ]

        return msg.reply(
            payload={"plan": plan},
            status=MessageStatus.COMPLETED if is_valid else MessageStatus.FAILED,
            next_action="EXECUTE" if is_valid else "REPLAN",
            evidence=evidence,
        )
