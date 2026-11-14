from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from nexo.core.llm_factory import get_llm_for_role
from nexo.tools.basic_tools import (
    leer_archivo,
    escribir_archivo,
    ejecutar_codigo_python,
)
import json
import re

from nexo.agents.base_agent import BaseAgent
from nexo.schemas.message import AgentID, MessageStatus, NexoMessage
from nexo.tools.diagnostic_tool import NetworkDiagnosticTool
from nexo.tools.system_tool import SystemDiagnosticTool
from nexo.tools.port_tool import PortCheckTool
from nexo.tools.base_tool import ToolRegistry
from nexo.tools.basic_tools import FileReadTool, FileWriteTool, extract_requested_file_content
from nexo.skills import SkillRegistry


class ExecutorAgent(BaseAgent):
    """Ejecutor NEXO: ejecuta diagnósticos autorizados y devuelve evidencia."""

    agent_id = AgentID.EXECUTOR

    def __init__(self, provider, bus):
        super().__init__(provider, bus)
        self.tools = ToolRegistry()
        self.tools.register(NetworkDiagnosticTool())
        self.tools.register(SystemDiagnosticTool())
        self.tools.register(PortCheckTool())
        self.tools.register(FileReadTool())
        self.tools.register(FileWriteTool())
        self.skills = SkillRegistry()

    @property
    def system_prompt(self) -> str:
        return """Interpreta los resultados reales de las herramientas, no inventes evidencia. Devuelve
JSON válido con task_executed, tool_used, steps, raw_results, interpretation, conclusion,
recommendation, confidence y can_complete."""

    def process(self, msg: NexoMessage) -> NexoMessage:
        subtask = msg.payload.get("subtask", {})
        task = subtask.get("task", msg.payload.get("task", "sin descripción"))
        tool_result = self._try_tool(task, msg.context)
        prompt = (
            f"Tarea: {task}\nResultado real de herramienta:\n"
            f"{json.dumps(tool_result, ensure_ascii=False, indent=2)}\n"
            f"Contexto: {json.dumps(msg.context, ensure_ascii=False)}\n"
            "Interpreta la evidencia y devuelve el JSON solicitado."
        )
        try:
            result = self.call_llm_json(prompt)
        except Exception as exc:
            self._log.warning("Executor interpretation failed; returning tool evidence: %s", exc)
            result = {"fallback_used": True, "interpretation_error": str(exc)}
        # Estos campos vienen de la herramienta, nunca del texto del modelo.
        result.update({
            "tool_used": tool_result.get("tool", "none"),
            "raw_results": tool_result.get("output", {}),
            "tool_success": bool(tool_result.get("success")),
            "tool_error": tool_result.get("error"),
            "task_executed": task,
            "steps": ["Herramienta ejecutada"] if tool_result.get("tool") != "none" else [],
            "conclusion": str(tool_result.get("output", {}).get("content", tool_result.get("output", {}).get("message", "Resultado registrado.")))[:500],
            "recommendation": "Evidencia obtenida por la herramienta." if tool_result.get("success") else "Corregir el error de la herramienta y reintentar.",
            "confidence": 0.8 if tool_result.get("success") else 0.0,
            "can_complete": bool(tool_result.get("success")) and tool_result.get("tool") != "none",
        })
        complete = bool(result["can_complete"])
        return msg.reply(
            payload={"execution_result": result},
            status=MessageStatus.COMPLETED if complete else MessageStatus.FAILED,
            next_action="EVALUATE" if complete else "REPLAN",
            evidence=[f"Herramienta: {result['tool_used']}", f"Conclusión: {result['conclusion'][:100]}"],
        )

    def _try_tool(self, task: str, context: dict) -> dict:
        skill = self.skills.select(task)
        tool_name = skill.tool_name if skill else None
        if skill and not self.skills.authorize(skill.name, self.agent_id.value, skill.permission):
            return {"tool": tool_name, "success": False, "error": "Operación bloqueada por Security Core", "output": {}}
        request = str(context.get("request", ""))
        if tool_name in {"file_write", "file_read"}:
            source = f"{request}\n{task}"
            match = re.search(r"(?:archivo|file)\s+(?:(?:llamado|llamada|named)\s+)?[`'\"]?([\w./-]+\.[\w-]+)", source, re.IGNORECASE)
            filename = match.group(1).strip("`'\".,;:") if match else "nexo_resultado.txt"
            if tool_name == "file_write":
                content = extract_requested_file_content(request)
                if content is None:
                    return {
                        "tool": "file_write", "success": False,
                        "error": "La solicitud no especifica un contenido de archivo inequívoco; no se escribió ningún dato.",
                        "output": {},
                    }
                return self.tools.execute_tool(tool_name, {"path": filename, "content": content})
            return self.tools.execute_tool(tool_name, {"path": filename})
        if tool_name == "system_diagnostic":
            return self.tools.execute_tool("system_diagnostic", context)
        if tool_name == "port_check":
            params = dict(context)
            params.setdefault("host", "8.8.8.8")
            params.setdefault("port", 53)
            return self.tools.execute_tool("port_check", params)
        if tool_name == "network_diagnostic":
            return self.tools.execute_tool("network_diagnostic", context)
        return {"tool": "none", "success": True, "output": {"message": "No se requirió herramienta específica"}}

    @staticmethod
    def resolve_tool_for_task(task: str) -> str | None:
        """Predice la herramienta del pipeline usando las mismas reglas de ejecución."""
        task_lower = task.lower()
        if any(word in task_lower for word in ("crear archivo", "escribir archivo", "guardar archivo", "write file", "create file")):
            return "file_write"
        if any(word in task_lower for word in ("leer archivo", "leer el archivo", "verificar archivo", "read file", "read the file")):
            return "file_read"
        if any(word in task_lower for word in ("sistema", "hardware", "disco", "cpu", "memoria", "espacio", "system_diagnostic")):
            return "system_diagnostic"
        if any(word in task_lower for word in ("puerto", "port", "tcp", "socket", "port_check")):
            return "port_check"
        if any(word in task_lower for word in ("red", "internet", "conexión", "ping", "dns", "gateway", "network", "wifi", "ethernet", "ip", "conectividad", "network_diagnostic")):
            return "network_diagnostic"
        return None


def crear_agente_ejecutor(config_dict: dict) -> AgentExecutor:
    """
    Crea y configura el Agente Ejecutor (Executor).
    Es el encargado de usar las herramientas para resolver las tareas técnicas.
    """
    # 1. Obtenemos el cerebro (Modelo Qwen configurado para el EXECUTOR)
    llm = get_llm_for_role("EXECUTOR", config_dict)

    # 2. Definimos las manos (Herramientas disponibles)
    tools = [leer_archivo, escribir_archivo, ejecutar_codigo_python]

    # 3. Definimos su personalidad y reglas de comportamiento (Prompt)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "Eres el Agente Ejecutor de NEXO, un experto programador y técnico de sistemas.\n"
                    "Tu trabajo es usar las herramientas disponibles para cumplir la tarea que se te asigne.\n"
                    "Piensa paso a paso. Si necesitas crear un archivo, hazlo. Si necesitas probar código, hazlo.\n"
                    "Responde siempre en español y explica brevemente lo que hiciste al final."
                ),
            ),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )

    # 4. Creamos el agente y lo envolvemos en el Ejecutor
    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=10,
        handle_parsing_errors=True,  # Evita que el agente se rompa si el modelo alucina un formato
    )

    return executor
