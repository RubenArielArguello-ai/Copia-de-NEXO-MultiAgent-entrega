"""
NEXO — Agente Analista.

Skill: Comprensión y análisis de problemas.

Responsabilidades:
  - Interpretar la solicitud del usuario
  - Identificar restricciones y limitaciones
  - Determinar qué información falta
  - Definir criterios de éxito medibles
  - Comunicar conclusiones al Orquestador
"""

from __future__ import annotations
import json

from nexo.agents.base_agent import BaseAgent
from nexo.schemas.message import (
    AgentID, MessageStatus, NexoMessage, TaskPhase
)


class AnalystAgent(BaseAgent):
    """
    Agente Analista de NEXO.

    Recibe la solicitud inicial del usuario y produce un análisis
    estructurado que el Estratega usará para planificar.
    """

    agent_id = AgentID.ANALYST

    @property
    def system_prompt(self) -> str:
        return """Eres el Agente Analista del sistema NEXO.

Tu rol es COMPRENDER y ANALIZAR problemas técnicos con precisión.

Cuando recibas una solicitud de servicio, debes producir un análisis estructurado en JSON con exactamente estos campos:

{
  "interpretation": "descripción clara del problema en tus propias palabras",
  "category": "categoría técnica del problema (ej: diagnóstico_red, falla_hardware, error_software)",
  "constraints": ["lista de restricciones o limitaciones del análisis"],
  "missing_info": ["información que falta para un diagnóstico completo"],
  "success_criteria": ["criterios medibles y verificables de éxito"],
  "priority": "alta|media|baja",
  "estimated_complexity": "simple|moderada|compleja",
  "initial_hypotheses": ["hipótesis iniciales sobre la causa"]
}

REGLAS:
- Responde SIEMPRE en JSON válido.
- No inventes información que no esté en la solicitud.
- Si algo no está claro, listalo en missing_info.
- Los criterios de éxito deben ser verificables, no vagos.
- Sé conciso pero completo."""

    def process(self, msg: NexoMessage) -> NexoMessage:
        """
        Analiza la solicitud del usuario y devuelve un análisis estructurado.
        """
        self._log.info("Analyzing request: %.80s...", msg.payload.get("request", ""))

        user_prompt = f"""Solicitud del usuario:
---
{msg.payload.get("request", "")}
---

Contexto y recuerdos recuperados (úsalos solo como referencia, nunca como evidencia de esta misión):
{json.dumps(msg.context, ensure_ascii=False)}

Produce el análisis estructurado."""

        try:
            analysis = self.call_llm_json(user_prompt)
        except Exception as exc:
            self._log.warning("Analyst inference failed; preserving the explicit request: %s", exc)
            analysis = {"parse_error": True, "fallback_used": True, "fallback_reason": str(exc)}
        if analysis.get("parse_error"):
            request = str(msg.payload.get("request", "")).strip()
            analysis = {
                "interpretation": request,
                "category": "solicitud_técnica",
                "constraints": ["Usar evidencia de herramientas; no asumir resultados"],
                "missing_info": [],
                "success_criteria": ["Completar la acción solicitada y verificarla con evidencia observable"],
                "priority": "media", "estimated_complexity": "simple",
                "initial_hypotheses": [], "fallback_used": True,
            }

        # Determinar si falta información crítica
        missing = analysis.get("missing_info", [])
        status  = (
            MessageStatus.PARTIAL
            if missing and len(missing) > 2
            else MessageStatus.COMPLETED
        )

        evidence = [
            f"Categoría identificada: {analysis.get('category', 'desconocida')}",
            f"Hipótesis iniciales: {len(analysis.get('initial_hypotheses', []))}",
            f"Criterios de éxito definidos: {len(analysis.get('success_criteria', []))}",
        ]

        return msg.reply(
            payload={"analysis": analysis},
            status=status,
            next_action="PLAN" if status == MessageStatus.COMPLETED else "REQUEST_INFO",
            evidence=evidence,
        )
