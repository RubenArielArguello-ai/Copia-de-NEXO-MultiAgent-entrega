from langchain_core.prompts import ChatPromptTemplate
from nexo.core.llm_factory import get_llm_for_role
import json
import re

from nexo.agents.base_agent import BaseAgent
from nexo.schemas.message import AgentID, MessageStatus, NexoMessage
from nexo.tools.basic_tools import extract_requested_file_content


def file_content_evidence_matches(request: str, execution_results: list[dict]) -> bool | None:
    """Return None for non-file requests; otherwise compare tool evidence literally."""
    is_file_write_request = bool(
        re.search(r"\b(?:archivo|file)\b", request, re.IGNORECASE)
        and re.search(r"\b(?:crear|crea|escribir|escribe|escribí|guardar|guarda|write|create)\b", request, re.IGNORECASE)
    )
    if not is_file_write_request:
        return None

    expected = extract_requested_file_content(request)
    writes = [
        item.get("result", {}) for item in execution_results
        if item.get("result", {}).get("tool_used") == "file_write"
    ]
    reads = [
        item.get("result", {}) for item in execution_results
        if item.get("result", {}).get("tool_used") == "file_read"
    ]
    has_exact_write = expected is not None and any(
        item.get("can_complete") is True
        and isinstance(item.get("raw_results"), dict)
        and item["raw_results"].get("content") == expected
        for item in writes
    )
    read_requested = bool(re.search(
        r"\b(?:leer|lee|leé|léelo|leelo|read|verificar|verifica|verify)\b",
        request, re.IGNORECASE,
    ))
    has_exact_read = expected is not None and any(
        item.get("can_complete") is True
        and isinstance(item.get("raw_results"), dict)
        and item["raw_results"].get("content") == expected
        for item in reads
    )
    return bool(has_exact_write and (not read_requested or has_exact_read))


class EvaluatorAgent(BaseAgent):
    """Agente de QA compatible con el protocolo y el bus de NEXO."""

    agent_id = AgentID.EVALUATOR

    @property
    def system_prompt(self) -> str:
        return """Evalúa evidencia frente al objetivo y criterios de éxito. No supongas que una tarea
se realizó si no hay resultados observables. Devuelve JSON válido con verdict (APPROVED,
NEEDS_CORRECTION o REJECTED), goal_achieved, evidence_quality, confidence, issues_found,
corrections_needed, summary y final_answer. Aprueba solo si hay evidencia suficiente."""

    def process(self, msg: NexoMessage) -> NexoMessage:
        execution_results = msg.payload.get("execution_results", [])
        analysis = msg.payload.get("analysis", {})
        user_prompt = (
            f"OBJETIVO ORIGINAL:\n{msg.context.get('original_request', msg.goal)}\n\n"
            f"CRITERIOS DE ÉXITO:\n{json.dumps(analysis.get('success_criteria', []), ensure_ascii=False)}\n\n"
            f"PLAN:\n{json.dumps(msg.payload.get('plan', []), ensure_ascii=False)}\n\n"
            f"RESULTADOS Y EVIDENCIA:\n{json.dumps(execution_results, ensure_ascii=False)}\n\n"
            "Evalúa evidencia concreta contra cada criterio. Responde solo JSON válido."
        )
        try:
            evaluation = self.call_llm_json(user_prompt)
        except Exception as exc:
            self._log.warning("Evaluator failed; rejecting without approval: %s", exc)
            evaluation = {"parse_error": True, "evaluation_error": str(exc)}
        if evaluation.get("parse_error"):
            evaluation = {
                **evaluation,
                "verdict": "REJECTED", "goal_achieved": False,
                "evidence_quality": "INSUFFICIENT", "confidence": 0.0,
                "issues_found": ["El Evaluador no pudo producir una evaluación estructurada"],
                "corrections_needed": [], "summary": "Resultado no aprobado: evaluación estructurada no disponible.",
            }
        verdict = str(evaluation.get("verdict", "REJECTED")).upper()
        if verdict not in {"APPROVED", "NEEDS_CORRECTION", "REJECTED"}:
            verdict = "REJECTED"
        # La aprobación requiere resultados exitosos con evidencia observada.
        if verdict == "APPROVED" and (
            not execution_results
            or any(not item.get("result", {}).get("can_complete", False) for item in execution_results)
        ):
            verdict = "REJECTED"
            evaluation["issues_found"] = list(evaluation.get("issues_found", [])) + [
                "No hay evidencia completa de herramienta para aprobar el objetivo"
            ]

        original_request = str(msg.context.get("original_request", msg.goal))
        file_evidence_matches = file_content_evidence_matches(original_request, execution_results)
        if file_evidence_matches is False:
            verdict = "REJECTED"
            evaluation["goal_achieved"] = False
            issues = evaluation.get("issues_found", [])
            if not isinstance(issues, list):
                issues = [str(issues)] if issues else []
            issues.append("La evidencia real de file_write/file_read no coincide exactamente con el contenido solicitado")
            evaluation["issues_found"] = issues
            corrections = evaluation.get("corrections_needed", [])
            if not isinstance(corrections, list):
                corrections = [str(corrections)] if corrections else []
            corrections.append("Escribir el contenido literal solicitado y volver a leerlo con file_read")
            evaluation["corrections_needed"] = corrections
        evaluation["verdict"] = verdict
        evaluation.setdefault("confidence", 0.0)
        evaluation.setdefault("issues_found", [])
        evaluation.setdefault("corrections_needed", [])
        answer = str(evaluation.get("final_answer", "")).strip()
        if not answer or answer.upper() == verdict or len(answer) < 20:
            answer = str(evaluation.get("summary", "")).strip()
            if not answer:
                answer = next((
                    str(item.get("result", {}).get("conclusion", "")).strip()
                    for item in reversed(execution_results)
                    if isinstance(item, dict) and item.get("result", {}).get("conclusion")
                ), "")
        evaluation["final_answer"] = answer or (
            "El Evaluador aprobó el resultado." if verdict == "APPROVED"
            else "El Evaluador no aprobó el resultado y se requieren correcciones."
        )
        status = MessageStatus.COMPLETED if verdict == "APPROVED" else (
            MessageStatus.PARTIAL if verdict == "NEEDS_CORRECTION" else MessageStatus.FAILED
        )
        return msg.reply(
            payload={"evaluation": evaluation}, status=status,
            next_action="DELIVER" if verdict == "APPROVED" else "REPLAN",
            evidence=[f"Veredicto: {verdict}", f"Problemas: {len(evaluation['issues_found'])}"],
        )


def evaluar_trabajo(objetivo: str, resultado_ejecutor: str, config_dict: dict) -> str:
    """
    Recibe el objetivo original y lo que hizo el Ejecutor.
    Devuelve 'APROBADO' o 'RECHAZADO' con razones.
    """
    # Usamos el modelo configurado para el EVALUATOR en tu config.py
    llm = get_llm_for_role("EVALUATOR", config_dict)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "Eres el Agente Evaluador de NEXO. Tu trabajo es ser un crítico estricto.\n"
                    "Revisarás el trabajo del Agente Ejecutor contra el objetivo original.\n"
                    "Empieza con una única etiqueta en la primera línea: APROBADO o RECHAZADO.\n"
                    "Después de la etiqueta explica brevemente evidencia y correcciones necesarias.\n"
                    "Aprueba solo cuando la evidencia presentada demuestre el objetivo."
                ),
            ),
            (
                "human",
                "OBJETIVO ORIGINAL:\n{objetivo}\n\nTRABAJO DEL EJECUTOR:\n{resultado}",
            ),
        ]
    )

    chain = prompt | llm
    respuesta = chain.invoke({"objetivo": objetivo, "resultado": resultado_ejecutor})
    return str(respuesta.content)


# Prueba rápida (opcional)
if __name__ == "__main__":
    config = {"EVALUATOR": {"type": "ollama", "model": "qwen2.5-coder:7b"}}
    print(evaluar_trabajo("Crear un hola mundo", "print('Hola')", config))
