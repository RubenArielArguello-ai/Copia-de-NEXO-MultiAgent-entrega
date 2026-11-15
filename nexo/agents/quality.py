"""Independent deterministic quality gate for task and evidence completeness."""
from nexo.agents.base_agent import BaseAgent
from nexo.schemas.message import AgentID, MessageStatus, NexoMessage


class QAAgent(BaseAgent):
    agent_id = AgentID.QA

    @property
    def system_prompt(self) -> str:
        return "Agente QA determinista: valida evidencia estructurada y completitud. No inventes resultados."

    def process(self, msg: NexoMessage) -> NexoMessage:
        planned = msg.payload.get("plan", [])
        results = msg.payload.get("execution_results", [])
        by_task = {item.get("task_id"): item.get("result", {}) for item in results if isinstance(item, dict)}
        checks = []
        for task in planned:
            result = by_task.get(task.get("id"), {})
            raw = result.get("raw_results")
            passed = bool(result.get("tool_success") and result.get("can_complete") and isinstance(raw, dict) and raw)
            checks.append({"task_id": task.get("id"), "tool": task.get("tool"), "passed": passed,
                           "reason": "evidencia observada" if passed else "faltan resultado exitoso o datos observados"})
        passed = bool(checks) and all(row["passed"] for row in checks)
        report_tools = {entry.get("tool") for item in results if isinstance(item, dict)
                        for entry in (item.get("result", {}).get("raw_results", {}).get("evidence", []) or [])
                        if isinstance(entry, dict) and entry.get("success")}
        required = {task.get("tool") for task in planned if task.get("tool") != "report_generation"}
        report_check = not any(task.get("tool") == "report_generation" for task in planned) or required.issubset(report_tools)
        passed = passed and report_check
        review = {"passed": passed, "checks": checks, "report_evidence_complete": report_check}
        return msg.reply({"quality_review": review}, status=MessageStatus.COMPLETED if passed else MessageStatus.PARTIAL,
                         next_action="EVALUATE" if passed else "CORRECT",
                         evidence=[f"QA checks: {sum(row['passed'] for row in checks)}/{len(checks)}", f"Report evidence: {report_check}"])
