"""Central skill metadata and least-privilege selection for NEXO."""
from dataclasses import dataclass
from typing import Any
import re


@dataclass(frozen=True)
class Skill:
    name: str
    version: str
    description: str
    tool_name: str
    agents: tuple[str, ...] = ("EXECUTOR",)
    permission: str = "read"
    keywords: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()


DEFAULT_SKILLS = (
    Skill("system_diagnostics", "1.0.0", "CPU, RAM, carga y disco", "system_diagnostic", keywords=("sistema", "cpu", "memoria", "ram", "disco", "servidor", "recursos", "hardware"), inputs=("path opcional",), outputs=("cpu", "ram", "disco", "procesos", "carga")),
    Skill("network_diagnostics", "1.0.0", "Interfaz, gateway, DNS y conectividad", "network_diagnostic", keywords=("red", "internet", "conectividad", "conexión", "dns", "wifi", "latencia"), inputs=("host_dns opcional",), outputs=("interfaz", "gateway", "dns", "internet", "diagnosis")),
    Skill("service_availability", "1.0.0", "Comprobación TCP de disponibilidad", "port_check", keywords=("puerto", "servicio", "tcp", "socket"), inputs=("host", "port"), outputs=("status", "latency", "details")),
    Skill("file_read", "1.0.0", "Lectura dentro del workspace", "file_read", permission="read", keywords=("leer archivo", "verificar archivo", "read file"), inputs=("path",), outputs=("content", "sha256")),
    Skill("file_write", "1.0.0", "Escritura dentro del workspace", "file_write", permission="write", keywords=("crear archivo", "escribir archivo", "guardar archivo", "write file"), inputs=("path", "content"), outputs=("path", "sha256")),
    Skill("log_analysis", "1.0.0", "Cuenta errores y patrones en logs dentro del workspace", "log_analysis", keywords=("analizar log", "analizar logs", "registro", "registros", "log analysis", "archivo de log"), inputs=("path",), outputs=("pattern_counts", "redacted_matches", "sha256")),
    Skill("http_health_check", "1.0.0", "Comprueba estado HTTP y tiempo de respuesta de una URL pública", "http_health_check", keywords=("api", "endpoint", "http", "https", "chequeo http", "health check", "estado de la api", "disponibilidad web"), inputs=("url", "timeout opcional"), outputs=("status_code", "healthy", "latency_ms")),
    Skill("code_engineering", "1.0.0", "Analiza sintaxis Python y patrones de riesgo sin ejecutar código", "code_engineering", keywords=("analizar código", "analiza el código", "revisar código", "revisa el código", "corregir código", "refactorizar", "pruebas de código", "code engineering"), inputs=("path",), outputs=("syntax_valid", "findings", "sha256")),
    Skill("report_generation", "1.0.0", "Consolida hallazgos y evidencia observada", "report_generation", keywords=("informe", "reporte", "report", "resumir resultados", "conclusiones"), inputs=("request", "prior_results"), outputs=("report_text", "evidence", "conclusion"), dependencies=("prior task evidence",)),
)


class SkillRegistry:
    """Discovers registered skills and enforces agent and operation permissions."""
    def __init__(self, skills=DEFAULT_SKILLS):
        self._skills = {skill.name: skill for skill in skills}
        self._history: list[dict[str, Any]] = []

    def list_skills(self) -> list[dict[str, Any]]:
        return [{"name": s.name, "version": s.version, "description": s.description,
                 "tool": s.tool_name, "agents": list(s.agents), "permission": s.permission,
                 "inputs": list(s.inputs), "outputs": list(s.outputs),
                 "dependencies": list(s.dependencies)}
                for s in self._skills.values()]

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def by_tool(self, tool_name: str) -> Skill | None:
        return next((skill for skill in self._skills.values() if skill.tool_name == tool_name), None)

    def select(self, task: str, agent: str = "EXECUTOR") -> Skill | None:
        text = task.casefold()
        explicit = [s for s in self._skills.values() if agent in s.agents and
                    (s.name.casefold() in text or s.tool_name.casefold() in text)]
        if explicit:
            return explicit[0]
        matches = [s for s in self._skills.values() if agent in s.agents and
                   any(word in text for word in s.keywords)]
        # Prefer specific file-write intent and avoid overloading agents with all skills.
        return max(matches, key=lambda s: max((len(k) for k in s.keywords if k in text), default=0)) if matches else None

    def select_all(self, text: str, agent: str = "EXECUTOR") -> list[Skill]:
        """Select each relevant capability once, in registry order."""
        folded = text.casefold()
        selected = []
        seen = set()
        for skill in self._skills.values():
            if agent not in skill.agents or skill.name in seen:
                continue
            file_hint = skill.name == "code_engineering" and bool(re.search(r"\.py\b", folded))
            log_hint = skill.name == "log_analysis" and bool(re.search(r"\.log\b", folded))
            if skill.name.casefold() in folded or skill.tool_name.casefold() in folded or file_hint or log_hint or any(k in folded for k in skill.keywords):
                selected.append(skill)
                seen.add(skill.name)
        return selected

    def resolve_tool(self, task: str, agent: str = "EXECUTOR") -> str | None:
        skill = self.select(task, agent)
        return skill.tool_name if skill else None

    def authorize(self, skill_name: str, agent: str, permission: str) -> bool:
        skill = self._skills.get(skill_name)
        allowed = bool(skill and agent in skill.agents and skill.permission == permission)
        self._history.append({"skill": skill_name, "agent": agent, "permission": permission, "allowed": allowed})
        return allowed

    @property
    def execution_history(self) -> list[dict[str, Any]]:
        return list(self._history)
