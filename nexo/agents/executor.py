"""
NEXO — Agente Ejecutor.

Skill: Resolución mediante herramientas.

Responsabilidades:
  - Ejecutar subtareas concretas asignadas por el Orquestador
  - Invocar herramientas disponibles (diagnóstico, consultas, etc.)
  - Registrar cada acción realizada con evidencia
  - Devolver resultados estructurados
  - Informar cuando no puede completar una tarea
"""

from __future__ import annotations
import json

from nexo.agents.base_agent import BaseAgent
from nexo.schemas.message import (
    AgentID, MessageStatus, NexoMessage, TaskPhase
)
from nexo.tools.diagnostic_tool import NetworkDiagnosticTool
from nexo.tools.system_tool import SystemDiagnosticTool
from nexo.tools.port_tool import PortCheckTool
from nexo.tools.base_tool import ToolRegistry


class ExecutorAgent(BaseAgent):
    """
    Agente Ejecutor de NEXO.

    Es el único agente que interactúa con herramientas reales.
    Usa qwen2.5-coder:7b por defecto para razonamiento técnico.
    """

    agent_id = AgentID.EXECUTOR

    def __init__(self, provider, bus):
        super().__init__(provider, bus)
        # Registro de herramientas autorizadas
        self.tools = ToolRegistry()
        self.tools.register(NetworkDiagnosticTool())
        self.tools.register(SystemDiagnosticTool())
        self.tools.register(PortCheckTool())

    @property
    def system_prompt(self) -> str:
        return """Eres el Agente Ejecutor del sistema NEXO.

Tu rol es EJECUTAR tareas técnicas concretas usando las herramientas disponibles.

Cuando recibas una tarea, debes:
1. Identificar qué herramienta usar.
2. Ejecutar la herramienta con los parámetros correctos.
3. Interpretar los resultados.
4. Producir una conclusión técnica.

Responde en JSON con exactamente estos campos:
{
  "task_executed": "descripción de la tarea realizada",
  "tool_used": "nombre de la herramienta",
  "steps": ["paso 1", "paso 2", ...],
  "raw_results": {"clave": "valor"},
  "interpretation": "interpretación técnica de los resultados",
  "conclusion": "conclusión principal",
  "recommendation": "acción recomendada basada en los resultados",
  "confidence": 0.0-1.0,
  "can_complete": true|false
}

HERRAMIENTAS DISPONIBLES:
- network_diagnostic: Diagnóstico de red completo (interfaz, gateway, DNS e Internet)
- system_diagnostic: Diagnóstico de hardware y OS (disco libre, CPU, carga y sistema)
- port_check: Verificación de puertos TCP específicos (ej: puerto 80, 443, 53)

REGLAS:
- Si una herramienta falla, reporta can_complete: false con la razón.
- No inventes resultados. Si no puedes ejecutar algo, dilo.
- Responde SIEMPRE en JSON válido."""

    def process(self, msg: NexoMessage) -> NexoMessage:
        """
        Ejecuta la tarea asignada usando las herramientas disponibles.
        """
        subtask = msg.payload.get("subtask", {})
        task_description = subtask.get("task", msg.payload.get("task", "sin descripción"))

        self._log.info("Executing task: %.80s", task_description)

        # Intentar ejecutar herramienta relevante
        tool_result = self._try_tool(task_description, msg.context)

        user_prompt = f"""Tarea asignada:
---
{task_description}
---

Resultado de herramienta ejecutada:
{json.dumps(tool_result, ensure_ascii=False, indent=2)}

Contexto del problema: {json.dumps(msg.context, ensure_ascii=False)}

Interpreta los resultados y produce la respuesta estructurada."""

        raw    = self.call_llm(user_prompt)
        result = self.parse_json_response(raw)

        # Si el LLM produjo un resultado sin el campo tool_used, completarlo
        if "tool_used" not in result and tool_result:
            result["tool_used"]   = tool_result.get("tool", "none")
            result["raw_results"] = tool_result.get("output", {})

        can_complete = result.get("can_complete", True)
        status       = MessageStatus.COMPLETED if can_complete else MessageStatus.FAILED

        evidence = [
            f"Herramienta: {result.get('tool_used', 'ninguna')}",
            f"Pasos ejecutados: {len(result.get('steps', []))}",
            f"Confianza: {result.get('confidence', 0)}",
            f"Conclusión: {result.get('conclusion', '')[:100]}",
        ]

        return msg.reply(
            payload={"execution_result": result},
            status=status,
            next_action="EVALUATE" if can_complete else "REPLAN",
            evidence=evidence,
        )

    def _try_tool(self, task: str, context: dict) -> dict:
        """
        Selecciona y ejecuta de forma segura la herramienta más apropiada para la tarea.
        """
        task_lower = task.lower()

        # 1. Diagnóstico de sistema / hardware / disco
        if any(kw in task_lower for kw in [
            "sistema", "hardware", "disco", "cpu", "memoria", "espacio", "carga", "load", "almacenamiento"
        ]):
            return self.tools.execute_tool("system_diagnostic", context)

        # 2. Verificación de puerto específico
        if any(kw in task_lower for kw in ["puerto", "port", "tcp", "socket"]):
            # Extraer host y puerto de contexto si existen, o usar defaults de red
            port_ctx = dict(context)
            if "host" not in port_ctx:
                port_ctx["host"] = "8.8.8.8"
            if "port" not in port_ctx:
                port_ctx["port"] = 53
            return self.tools.execute_tool("port_check", port_ctx)

        # 3. Diagnóstico de red general (L1 a L4)
        if any(kw in task_lower for kw in [
            "red", "internet", "conexión", "ping", "dns", "gateway",
            "network", "interface", "wifi", "ethernet", "ip",
            "conectividad", "resolución", "domain"
        ]):
            return self.tools.execute_tool("network_diagnostic", context)

        return {"tool": "none", "output": {"message": "No se requirió herramienta específica"}}
