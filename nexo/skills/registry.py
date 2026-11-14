"""Central skill metadata and least-privilege selection for NEXO."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Skill:
    name: str
    version: str
    description: str
    tool_name: str
    agents: tuple[str, ...] = ("EXECUTOR",)
    permission: str = "read"
    keywords: tuple[str, ...] = ()


DEFAULT_SKILLS = (
    Skill("system_diagnostics", "1.0.0", "CPU, carga y disco", "system_diagnostic", keywords=("sistema", "cpu", "memoria", "disco", "servidor", "recursos", "hardware")),
    Skill("network_diagnostics", "1.0.0", "Interfaz, gateway, DNS y conectividad", "network_diagnostic", keywords=("red", "internet", "conectividad", "conexión", "dns", "wifi", "latencia")),
    Skill("service_availability", "1.0.0", "Comprobación TCP de disponibilidad", "port_check", keywords=("puerto", "servicio", "tcp", "socket")),
    Skill("file_read", "1.0.0", "Lectura dentro del workspace", "file_read", permission="read", keywords=("leer archivo", "verificar archivo", "read file")),
    Skill("file_write", "1.0.0", "Escritura dentro del workspace", "file_write", permission="write", keywords=("crear archivo", "escribir archivo", "guardar archivo", "write file")),
)


class SkillRegistry:
    """Discovers registered skills and enforces agent and operation permissions."""
    def __init__(self, skills=DEFAULT_SKILLS):
        self._skills = {skill.name: skill for skill in skills}
        self._history: list[dict[str, Any]] = []

    def list_skills(self) -> list[dict[str, Any]]:
        return [{"name": s.name, "version": s.version, "description": s.description,
                 "tool": s.tool_name, "agents": list(s.agents), "permission": s.permission}
                for s in self._skills.values()]

    def select(self, task: str, agent: str = "EXECUTOR") -> Skill | None:
        text = task.casefold()
        matches = [s for s in self._skills.values() if agent in s.agents and
                   (s.name.casefold() in text or s.tool_name.casefold() in text or
                    any(word in text for word in s.keywords))]
        # Prefer specific file-write intent and avoid overloading agents with all skills.
        return max(matches, key=lambda s: max((len(k) for k in s.keywords if k in text), default=0)) if matches else None

    def authorize(self, skill_name: str, agent: str, permission: str) -> bool:
        skill = self._skills.get(skill_name)
        allowed = bool(skill and agent in skill.agents and skill.permission == permission)
        self._history.append({"skill": skill_name, "agent": agent, "permission": permission, "allowed": allowed})
        return allowed

    @property
    def execution_history(self) -> list[dict[str, Any]]:
        return list(self._history)
