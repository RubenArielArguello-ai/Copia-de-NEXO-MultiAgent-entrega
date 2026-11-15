"""Independent fail-closed review of tool execution authorization evidence."""
from nexo.agents.base_agent import BaseAgent
from nexo.schemas.message import AgentID, MessageStatus, NexoMessage
from nexo.skills import SkillRegistry


class SecurityAgent(BaseAgent):
    agent_id = AgentID.SECURITY

    @property
    def system_prompt(self) -> str:
        return "Agente Security de NEXO: aplica mínimo privilegio y bloquea ejecuciones sin autorización trazable."

    def process(self, msg: NexoMessage) -> NexoMessage:
        registry = SkillRegistry()
        checks = []
        for item in msg.payload.get("execution_results", []):
            if not isinstance(item, dict):
                continue
            result = item.get("result", {})
            raw = result.get("raw_results") if isinstance(result, dict) else None
            audit = raw.get("skill_audit") if isinstance(raw, dict) else None
            tool = result.get("tool_used") if isinstance(result, dict) else None
            skill = registry.by_tool(str(tool))
            allowed = bool(skill and isinstance(audit, dict) and audit.get("authorized") is True
                           and audit.get("skill") == skill.name and audit.get("agent") == "EXECUTOR"
                           and audit.get("permission") == skill.permission)
            checks.append({"task_id": item.get("task_id"), "tool": tool, "skill": skill.name if skill else None,
                           "permission": audit.get("permission") if isinstance(audit, dict) else None,
                           "authorized": allowed})
        passed = bool(checks) and all(check["authorized"] for check in checks)
        review = {"passed": passed, "checks": checks,
                  "blocked_reason": None if passed else "Ejecución sin Skill y permiso verificables"}
        return msg.reply({"security_review": review}, status=MessageStatus.COMPLETED if passed else MessageStatus.FAILED,
                         next_action="EVALUATE" if passed else "BLOCK",
                         evidence=[f"Ejecuciones autorizadas: {sum(row['authorized'] for row in checks)}/{len(checks)}"])
