"""
NEXO — Agente Evaluador.

Skill: Verificación y control de calidad.

Responsabilidades:
  - Evaluar los resultados de ejecución contra el objetivo original
  - Detectar inconsistencias y contradicciones
  - Verificar que la evidencia sea suficiente
  - Solicitar correcciones si el resultado es incompleto
  - Evitar que el sistema declare éxito sin evidencia suficiente
"""

from __future__ import annotations
import json

from nexo.agents.base_agent import BaseAgent
from nexo.schemas.message import (
    AgentID, MessageStatus, NexoMessage, TaskPhase
)


class EvaluatorAgent(BaseAgent):
    """
    Agente Evaluador de NEXO.

    Es el guardián de la calidad. No permite que el sistema
    entregue resultados no verificados o contradictorios.
    """

    agent_id = AgentID.EVALUATOR

    @property
    def system_prompt(self) -> str:
        return """Eres el Agente Evaluador del sistema NEXO.

Tu rol es VERIFICAR que los resultados sean correctos, completos y consistentes.

Eres CRÍTICO y EXIGENTE. No permites que el sistema declare éxito sin evidencia.

Dado un conjunto de resultados y el objetivo original, produce una evaluación en JSON:

{
  "verdict": "APPROVED|REJECTED|NEEDS_CORRECTION",
  "goal_achieved": true|false,
  "evidence_quality": "SUFFICIENT|INSUFFICIENT|CONTRADICTORY",
  "confidence": 0.0-1.0,
  "issues_found": [
    {
      "type": "INCONSISTENCY|MISSING_EVIDENCE|GOAL_MISMATCH|PARTIAL_RESULT",
      "description": "descripción del problema",
      "severity": "critical|major|minor"
    }
  ],
  "corrections_needed": ["corrección 1", "corrección 2"],
  "summary": "resumen ejecutivo de la evaluación",
  "final_answer": "respuesta final para el usuario (solo si verdict=APPROVED)"
}

REGLAS DE EVALUACIÓN:
1. RECHAZA si el resultado contradice el objetivo original.
2. RECHAZA si la evidencia es vaga o no verificable.
3. APRUEBA solo si los criterios de éxito están cumplidos.
4. NECESITA_CORRECCIÓN si es parcialmente correcto pero mejorable.
5. El campo final_answer debe ser una respuesta clara y útil para el usuario final.
6. Responde SIEMPRE en JSON válido."""

    def process(self, msg: NexoMessage) -> NexoMessage:
        """
        Evalúa todos los resultados de la sesión contra el objetivo original.
        """
        execution_results = msg.payload.get("execution_results", [])
        analysis          = msg.payload.get("analysis", {})
        plan              = msg.payload.get("plan", {})

        self._log.info("Evaluating %d execution results", len(execution_results))

        user_prompt = f"""OBJETIVO ORIGINAL:
{msg.goal}

ANÁLISIS PREVIO:
{json.dumps(analysis, ensure_ascii=False, indent=2)}

PLAN EJECUTADO:
{json.dumps(plan, ensure_ascii=False, indent=2)}

RESULTADOS DE EJECUCIÓN:
{json.dumps(execution_results, ensure_ascii=False, indent=2)}

CRITERIOS DE ÉXITO DEFINIDOS:
{json.dumps(analysis.get("success_criteria", []), ensure_ascii=False)}

Evalúa si el objetivo fue cumplido y produce tu veredicto."""

        raw        = self.call_llm(user_prompt)
        evaluation = self.parse_json_response(raw)

        verdict  = evaluation.get("verdict", "REJECTED")
        approved = verdict == "APPROVED"

        status = (
            MessageStatus.COMPLETED if approved
            else MessageStatus.PARTIAL if verdict == "NEEDS_CORRECTION"
            else MessageStatus.FAILED
        )

        issues   = evaluation.get("issues_found", [])
        evidence = [
            f"Veredicto: {verdict}",
            f"Confianza: {evaluation.get('confidence', 0):.0%}",
            f"Problemas encontrados: {len(issues)}",
            f"Calidad de evidencia: {evaluation.get('evidence_quality', 'unknown')}",
        ]

        return msg.reply(
            payload={"evaluation": evaluation},
            status=status,
            next_action=(
                "DELIVER"  if approved
                else "REPLAN" if verdict == "NEEDS_CORRECTION"
                else "REPLAN"
            ),
            evidence=evidence,
        )
