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
  "max_steps": 5
}

REGLAS:
- Cada tarea debe ser ATÓMICA (una sola responsabilidad).
- Las dependencias deben ser correctas: T2 no puede depender de T3 si T3 no existe aún.
- Asigna tareas de diagnóstico técnico siempre a EXECUTOR.
- Asigna tareas de verificación a EVALUATOR.
- Mantén el plan MINIMALISTA: no más de 6 tareas para problemas simples.
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

Genera el plan de acción."""

        raw  = self.call_llm(user_prompt)
        plan = self.parse_json_response(raw)

        # Validación básica: debe tener al menos una tarea
        tasks    = plan.get("plan", [])
        is_valid = len(tasks) > 0

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
