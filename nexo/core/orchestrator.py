"""
NEXO — Orquestador Central.

El Orquestador es el director cognitivo del sistema. Es responsable de:

  1. MANTENER el objetivo común en todo momento
  2. COMPRENDER el estado global de la tarea
  3. DECIDIR qué agente interviene en cada etapa
  4. DISTRIBUIR subtareas con contexto adecuado
  5. COORDINAR la comunicación entre agentes
  6. GESTIONAR dependencias entre subtareas
  7. DETECTAR bloqueos y situaciones de fallo
  8. SOLICITAR revisiones cuando el Evaluador las detecta
  9. DECIDIR cuándo el objetivo está cumplido
  10. EVITAR ciclos infinitos de razonamiento

El Orquestador implementa el ciclo cognitivo completo:
Percepción → Análisis → Planificación → Ejecución → Evaluación → [Corrección] → Entrega
"""

from __future__ import annotations
import logging
import time
from typing import Any, Optional

from nexo.core.state_manager import StateManager, SessionState, SubTask, SessionStatus
from nexo.core.message_bus import MessageBus
from nexo.agents.analyst    import AnalystAgent
from nexo.agents.strategist import StrategistAgent
from nexo.agents.executor   import ExecutorAgent
from nexo.agents.evaluator  import EvaluatorAgent
from nexo.agents.researcher import ResearcherAgent
from nexo.agents.quality import QAAgent
from nexo.agents.security import SecurityAgent
from nexo.tools.coherence_monitor import CoherenceMonitor
from nexo.skills import SkillRegistry
from nexo.core.harness import MissionHarness
from nexo.schemas.message import (
    NexoMessage, AgentID, MessageStatus, TaskPhase, CoherenceFlag
)
from nexo.providers.base_provider import build_provider, MockProvider
from nexo.config import PROVIDER_CONFIG, ORCHESTRATOR_CONFIG

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Orquestador central de NEXO.

    Gestiona el ciclo completo de resolución de una solicitud,
    coordinando los 4 agentes especializados.
    """

    def __init__(self, state_manager: StateManager, provider_config: Optional[dict] = None):
        self.state_manager     = state_manager
        self.provider_config   = provider_config or PROVIDER_CONFIG
        self.coherence_monitor = CoherenceMonitor()
        self.skill_registry = SkillRegistry()
        self.max_iterations    = ORCHESTRATOR_CONFIG["max_iterations"]
        self.max_replanning    = ORCHESTRATOR_CONFIG["max_replanning_cycles"]
        self.coherence_thr     = ORCHESTRATOR_CONFIG["coherence_threshold"]
        self._log              = logging.getLogger("nexo.orchestrator")
        self.harness: MissionHarness | None = None

    # ──────────────────────────────────────────────────────────────────
    # Punto de entrada público
    # ──────────────────────────────────────────────────────────────────

    def run(self, session_id: str) -> dict[str, Any]:
        """
        Ejecuta el ciclo completo de resolución para una sesión.

        Devuelve un dict con el resultado final, métricas y estado.
        """
        session = self.state_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Sesión {session_id} no encontrada")

        start_time  = time.time()
        replan_count = 0
        self.harness = MissionHarness(
            session_id,
            timeout_seconds=ORCHESTRATOR_CONFIG["timeout_seconds"],
            max_tasks=ORCHESTRATOR_CONFIG["max_tool_executions"],
            max_llm_calls=ORCHESTRATOR_CONFIG["max_llm_calls"],
        )
        session.agent_results["harness"] = self.harness.snapshot()

        self._log.info("=== NEXO SESSION START [%s] ===", session_id[:8])
        self._log.info("Request: %.100s", session.original_request)

        # Inicializar bus de mensajes para esta sesión
        bus = MessageBus(session_id)
        bus.save_session(session.original_request, "RUNNING", session.to_summary())

        session.status = SessionStatus.RUNNING

        try:
            self.harness.check_active()
            # Construir agentes con sus proveedores. Una configuración real de
            # Ollama que no esté disponible falla aquí; no se sustituye por mock.
            agents = self._build_agents(bus)
            for agent in agents.values():
                agent.harness = self.harness
            session.agent_results["mock_mode"] = all(
                isinstance(agent.provider, MockProvider) for agent in agents.values()
            )
            session.agent_results["models_used"] = {
                agent.agent_id.value: (
                    getattr(agent.provider, "model", None)
                    or getattr(agent.provider, "last_telemetry", {}).get("model")
                    or f"mock-{agent.agent_id.value.lower()}"
                )
                for agent in agents.values()
                if agent.agent_id not in {AgentID.QA, AgentID.SECURITY}
            }
            session.agent_results["internal_agents"] = {
                "QA": "deterministic-evidence-policy",
                "SECURITY": "deterministic-least-privilege-policy",
            }
            session.agent_results["memory_context"] = self._load_memory_context(session, agents)

            # ── FASE 1: PERCEPCIÓN + ANÁLISIS ─────────────────────────
            analysis = self._phase_analysis(session, bus, agents)
            self.harness.check_active()
            if not analysis or analysis.get("parse_error"):
                return self._fail(session, bus, "El Analista no pudo interpretar la solicitud")

            # ── FASE 2: PLANIFICACIÓN ─────────────────────────────────
            plan = self._phase_planning(session, bus, agents, analysis)
            self.harness.check_active()
            if not plan:
                return self._fail(session, bus, "El Estratega no pudo generar un plan")

            # ── CICLO: EJECUCIÓN + EVALUACIÓN + CORRECCIÓN ────────────
            while session.iteration < self.max_iterations:
                self.harness.check_active()
                session.iteration = self.state_manager.increment_iteration(session_id)
                self._log.info("--- Iteration %d/%d ---", session.iteration, self.max_iterations)

                # ── NCM: Verificación de coherencia ───────────────────
                coherence = self._run_coherence_check(session, bus)
                session.coherence_score = coherence["coherence_score"]

                if coherence["cycle_risk"]:
                    self._log.warning("Cycle risk detected. Forcing delivery.")
                    break

                if coherence["should_replan"] and replan_count < self.max_replanning:
                    replan_count += 1
                    self._log.warning("Coherence issue — replanning (%d)", replan_count)
                    session.status = SessionStatus.REPLANNING
                    plan = self._phase_planning(session, bus, agents, analysis)
                    if not plan:
                        break

                # ── FASE 3: EJECUCIÓN ─────────────────────────────────
                execution_results = self._phase_execution(session, bus, agents, plan)

                # El Investigador se usa cuando hay una misión compuesta y
                # sintetiza solo resultados observados, nunca como evidencia.
                selected_skills = self.skill_registry.select_all(session.original_request)
                if len(selected_skills) > 1 or str(analysis.get("estimated_complexity", "")).casefold() == "compleja":
                    research = self._run_aux_agent(
                        session, bus, agents["researcher"], "researcher",
                        TaskPhase.RESEARCH,
                        {"analysis": analysis, "execution_results": execution_results},
                    )
                    if research:
                        session.agent_results["research"] = research.get("research", {})

                # QA y Security son gates independientes previos al Evaluador.
                quality = self._run_aux_agent(
                    session, bus, agents["qa"], "qa", TaskPhase.QUALITY,
                    {"plan": plan, "execution_results": execution_results},
                )
                if quality:
                    session.agent_results["quality_review"] = quality.get("quality_review", {})
                security = self._run_aux_agent(
                    session, bus, agents["security"], "security", TaskPhase.SECURITY,
                    {"execution_results": execution_results},
                )
                if security:
                    session.agent_results["security_review"] = security.get("security_review", {})

                # ── FASE 4: EVALUACIÓN ────────────────────────────────
                evaluation = self._phase_evaluation(
                    session, bus, agents, analysis, plan, execution_results
                )

                verdict = evaluation.get("verdict", "REJECTED")
                self._log.info("Evaluator verdict: %s", verdict)

                if verdict == "APPROVED":
                    # ── FASE 10: ENTREGA ──────────────────────────────
                    self.state_manager.set_phase(session.session_id, TaskPhase.DELIVERY)
                    session.final_answer = (
                        evaluation.get("final_answer")
                        or evaluation.get("summary")
                        or self._extract_best_answer(execution_results)
                    )
                    session.status       = SessionStatus.COMPLETED
                    self._remember_approved_result(session, execution_results)
                    break

                elif verdict in ("NEEDS_CORRECTION", "REJECTED") and replan_count < self.max_replanning:
                    replan_count += 1
                    self._log.info("Correction needed (%s) — replanning (%d)", verdict, replan_count)
                    session.status = SessionStatus.REPLANNING
                    self.state_manager.set_phase(session.session_id, TaskPhase.CORRECTION)

                    # Pasar correcciones y problemas detectados para la replanificación
                    issues = [item.get("description", str(item)) if isinstance(item, dict) else str(item)
                              for item in evaluation.get("issues_found", [])]
                    analysis["corrections"] = evaluation.get("corrections_needed", []) + issues

                    plan = self._phase_planning(session, bus, agents, analysis)
                    if not plan:
                        break

                else:
                    # Fallo definitivo o se agotaron las replanificaciones
                    self._log.warning("Cannot approve — delivering best available result")
                    self.state_manager.set_phase(session.session_id, TaskPhase.DELIVERY)
                    session.final_answer = (
                        evaluation.get("final_answer")
                        or evaluation.get("summary")
                        or self._extract_best_answer(execution_results)
                    )
                    session.status = SessionStatus.COMPLETED
                    break

        except Exception as e:
            self._log.error("Unexpected error: %s", e, exc_info=True)
            return self._fail(session, bus, str(e))

        # El circuit breaker también debe cerrar la sesión cuando alcanza el
        # máximo de iteraciones o detecta riesgo de ciclo antes de ejecutar.
        if session.status in (SessionStatus.RUNNING, SessionStatus.REPLANNING):
            available_results = session.agent_results.get("execution", [])
            session.final_answer = self._extract_best_answer(available_results)
            session.final_answer = (
                "Resultado no aprobado por el Evaluador. Mejor resultado disponible: "
                + session.final_answer
            )
            self.state_manager.set_phase(session.session_id, TaskPhase.DELIVERY)
            session.status = SessionStatus.COMPLETED

        # ── Métricas finales ──────────────────────────────────────────
        elapsed = time.time() - start_time
        if self.harness:
            self.harness.finish("failed" if session.status == SessionStatus.FAILED else "completed")
        harness_summary = self.harness.snapshot() if self.harness else {}
        session.agent_results["harness"] = harness_summary
        session.agent_results["llm_usage"] = {
            agent.agent_id.value: dict(agent.llm_usage)
            for agent in agents.values()
            if getattr(agent, "llm_usage", {}).get("calls", 0)
        }
        session.metrics.update({
            "end_time":       time.time(),
            "elapsed_seconds": round(elapsed, 2),
            "iterations":     session.iteration,
            "replan_count":   replan_count,
            "coherence_score": session.coherence_score,
            "message_count":  len(session.messages),
            "harness_tasks_started": harness_summary.get("tasks_started", 0),
            "harness_blocked_operations": harness_summary.get("blocked_operations", 0),
        })

        self._log.info(
            "=== SESSION COMPLETE [%s] | %.2fs | iter=%d | score=%.2f ===",
            session_id[:8], elapsed, session.iteration, session.coherence_score
        )

        result = {
            "session_id":     session_id,
            "original_request": session.original_request,
            "status":         session.status.value,
            "current_phase":  session.current_phase.value,
            "iteration":      session.iteration,
            "final_answer":   session.final_answer,
            "approved":       session.agent_results.get("evaluation", {}).get("verdict") == "APPROVED",
            "verdict":        session.agent_results.get("evaluation", {}).get("verdict", "UNKNOWN"),
            "agent_results":  session.agent_results,
            "error_log":      list(session.error_log),
            "memory_context": session.agent_results.get("memory_context", ""),
            "coherence_score": session.coherence_score,
            "metrics":        session.metrics,
            "messages":       [m.to_dict() for m in session.messages],
            "plan":           [
                {
                    "id":          st.task_id,
                    "description": st.description,
                    "agent":       st.assigned_to,
                    "status":      st.status,
                    "tool":        st.tool_name,
                    "skill":       st.skill_name,
                    "permission":  st.permission,
                }
                for st in session.plan
            ],
            "plan_detail": [
                {
                    "id": st.task_id,
                    "description": st.description,
                    "agent": st.assigned_to,
                    "status": st.status,
                    "depends_on": st.depends_on,
                    "tool": st.tool_name,
                    "skill": st.skill_name,
                    "permission": st.permission,
                }
                for st in session.plan
            ],
        }

        bus.save_session(session.original_request, session.status.value, result)
        return result

    # ──────────────────────────────────────────────────────────────────
    # Fases del ciclo cognitivo
    # ──────────────────────────────────────────────────────────────────

    def _phase_analysis(
        self, session: SessionState, bus: MessageBus, agents: dict
    ) -> Optional[dict]:
        """
        FASE 1: Percepción + Interpretación.
        El Orquestador envía la solicitud al Analista.
        """
        self._log.info("[PHASE] ANALYSIS")
        self.state_manager.set_phase(session.session_id, TaskPhase.ANALYSIS)

        msg = NexoMessage(
            from_agent=AgentID.ORCHESTRATOR,
            to_agent=AgentID.ANALYST,
            task_id=session.session_id,
            goal=session.original_request,
            phase=TaskPhase.ANALYSIS,
            payload={"request": session.original_request},
            context={
                "session_id": session.session_id,
                "memory_context": session.agent_results.get("memory_context", ""),
            },
            status=MessageStatus.PENDING,
            next_action="ANALYZE",
        )
        bus.publish(msg)
        session.add_message(msg)

        # El Analista procesa el mensaje
        response = agents["analyst"].run()
        if response:
            session.add_message(response)
            analysis = response.payload.get("analysis", {})
            session.goal = analysis.get("interpretation", session.original_request)
            session.agent_results["analysis"] = analysis
            return analysis
        return None

    def _phase_planning(
        self,
        session: SessionState,
        bus: MessageBus,
        agents: dict,
        analysis: dict,
    ) -> Optional[list[dict]]:
        """
        FASE 2: Planificación.
        El Orquestador solicita un plan al Estratega.
        """
        self._log.info("[PHASE] PLANNING")
        self.state_manager.set_phase(session.session_id, TaskPhase.PLANNING)

        msg = NexoMessage(
            from_agent=AgentID.ORCHESTRATOR,
            to_agent=AgentID.STRATEGIST,
            task_id=session.session_id,
            goal=session.goal or session.original_request,
            phase=TaskPhase.PLANNING,
            payload={"analysis": analysis},
            context={
                "session_id":  session.session_id,
                "corrections": analysis.get("corrections", []),
            },
            status=MessageStatus.PENDING,
            next_action="PLAN",
        )
        bus.publish(msg)
        session.add_message(msg)

        response = agents["strategist"].run()
        if response:
            session.add_message(response)
            plan_data = response.payload.get("plan", {})
            proposed_tasks = plan_data.get("plan", [])
            tasks = []
            excluded = []
            selected_tools = set()
            eligible_ids = set()

            # Una solicitud compuesta de crear y luego leer un archivo se
            # convierte en dos operaciones reales para respetar el orden y
            # verificar el contenido que se escribió.
            request_text = session.original_request
            if any(term in request_text.lower() for term in ("archivo", "file")) and any(term in request_text.lower() for term in ("crea", "crear", "escrib", "guarda", "create", "write")) and any(term in request_text.lower() for term in ("lee", "leer", "léelo", "leelo", "read")):
                proposed_tasks = [
                    {"id": "T1", "task": f"Crear archivo solicitado. Objetivo completo: {request_text}", "agent": "EXECUTOR", "depends_on": [], "tool": "file_write"},
                    {"id": "T2", "task": f"Leer el archivo creado y verificar su contenido. Objetivo completo: {request_text}", "agent": "EXECUTOR", "depends_on": ["T1"], "tool": "file_read"},
                ]

            # El orquestador ya tiene una fase de evaluación. Solo se delegan al
            # Ejecutor subtareas que correspondan a una herramienta real y única;
            # así no se ejecutan subtareas de resumen/revisión como si fueran acciones.
            requested_skills = self.skill_registry.select_all(request_text)
            proposed_names = {agents["executor"].resolve_tool_for_task(str(item.get("task", "")))
                              for item in proposed_tasks if isinstance(item, dict)}
            for skill in requested_skills:
                if skill.tool_name not in proposed_names:
                    proposed_tasks.append({"id": f"S{len(proposed_tasks)+1}",
                                           "task": f"{skill.name}: {request_text}",
                                           "agent": "EXECUTOR", "depends_on": []})
                    proposed_names.add(skill.tool_name)

            for task in proposed_tasks:
                task = dict(task)
                task_id = task.get("id", "T?")
                if str(task.get("agent", "EXECUTOR")).upper() != "EXECUTOR":
                    excluded.append({"id": task_id, "task": task.get("task", ""), "reason": "la evaluación se realiza en la fase del Evaluador"})
                    continue
                # Respeta la herramienta pre-asignada (casos compuestos archivo write→read)
                # y solo resuelve por LLM cuando no está declarada.
                tool_name = task.get("tool") or agents["executor"].resolve_tool_for_task(task.get("task", ""))
                if tool_name is None:
                    excluded.append({"id": task_id, "task": task.get("task", ""), "reason": "no corresponde a una herramienta ejecutable del pipeline"})
                    continue
                if tool_name in selected_tools:
                    excluded.append({"id": task_id, "task": task.get("task", ""), "reason": f"acción duplicada: {tool_name}"})
                    continue
                task["agent"] = "EXECUTOR"
                task["tool"] = tool_name
                selected_tools.add(tool_name)
                eligible_ids.add(task_id)
                tasks.append(task)

            tasks.sort(key=lambda item: item.get("tool") == "report_generation")
            for task in tasks:
                task["depends_on"] = [dep for dep in task.get("depends_on", []) if dep in eligible_ids]

            plan_data["proposed_plan"] = proposed_tasks
            plan_data["plan"] = tasks
            plan_data["excluded_tasks"] = excluded
            if excluded:
                self._log.info("Plan normalized: kept %d executable task(s), excluded %d non-executable/duplicate task(s)", len(tasks), len(excluded))

            # Registrar el plan en el estado de sesión
            session.plan.clear()
            for task in tasks:
                skill = self.skill_registry.by_tool(task.get("tool", ""))
                session.add_subtask(SubTask(
                    task_id=task.get("id", "T?"),
                    description=task.get("task", ""),
                    assigned_to=task.get("agent", "EXECUTOR"),
                    depends_on=task.get("depends_on", []),
                    tool_name=task.get("tool"),
                    skill_name=skill.name if skill else None,
                    permission=skill.permission if skill else None,
                ))
            session.agent_results["plan"] = plan_data
            return tasks
        return None

    def _phase_execution(
        self,
        session: SessionState,
        bus: MessageBus,
        agents: dict,
        plan: list[dict],
    ) -> list[dict]:
        """
        FASE 3: Ejecución.
        El Orquestador asigna subtareas al Ejecutor respetando dependencias.
        """
        self._log.info("[PHASE] EXECUTION")
        self.state_manager.set_phase(session.session_id, TaskPhase.EXECUTION)

        results = []
        completed_tasks = set()
        previous_by_tool = {
            item.get("result", {}).get("tool_used"): item.get("result", {})
            for item in session.agent_results.get("execution", [])
            if isinstance(item, dict) and item.get("result", {}).get("can_complete")
        }

        for task in plan:
            if self.harness:
                self.harness.check_active()
            task_id  = task.get("id", "?")
            agent    = task.get("agent", "EXECUTOR")
            deps     = task.get("depends_on", [])
            planned_tool = task.get("tool") or agents["executor"].resolve_tool_for_task(task.get("task", ""))

            # Preserve completed evidence across replans; rerun only failed or
            # explicitly regenerated report tasks.
            prior = previous_by_tool.get(planned_tool)
            if prior and planned_tool != "report_generation" and prior.get("tool_success"):
                results.append({"task_id": task_id, "result": prior})
                completed_tasks.add(task_id)
                session.update_subtask(task_id, "done", prior)
                continue

            # Verificar dependencias
            if not all(dep in completed_tasks for dep in deps):
                self._log.warning("Task %s skipped: unmet dependencies %s", task_id, deps)
                session.update_subtask(task_id, "failed", {"error": "dependencia no satisfecha"})
                continue

            if agent == "EXECUTOR":
                if self.harness:
                    self.harness.begin_task(task_id, agent, planned_tool or "unresolved")
                    session.agent_results["harness"] = self.harness.snapshot()
                session.update_subtask(task_id, "active")

                msg = NexoMessage(
                    from_agent=AgentID.ORCHESTRATOR,
                    to_agent=AgentID.EXECUTOR,
                    task_id=session.session_id,
                    goal=session.goal,
                    phase=TaskPhase.EXECUTION,
                    payload={
                        "subtask": task,
                        "task":    task.get("task", ""),
                    },
                    context={
                        "session_id":    session.session_id,
                        "request":       session.original_request,
                        "analysis":      session.agent_results.get("analysis", {}),
                        "prior_results": results,
                    },
                    status=MessageStatus.PENDING,
                    next_action="EXECUTE",
                    iteration=session.iteration,
                )
                bus.publish(msg)
                session.add_message(msg)

                response = agents["executor"].run()
                if response:
                    session.add_message(response)
                    exec_result = response.payload.get("execution_result", {})
                    results.append({"task_id": task_id, "result": exec_result})
                    if self.harness:
                        self.harness.finish_task(
                            task_id, agent, exec_result.get("tool_used", planned_tool or "unknown"),
                            bool(exec_result.get("tool_success")),
                            float(exec_result.get("tool_duration_ms", 0)),
                            skill_audit=exec_result.get("raw_results", {}).get("skill_audit")
                            if isinstance(exec_result.get("raw_results"), dict) else None,
                            error=exec_result.get("tool_error"),
                        )
                        session.agent_results["harness"] = self.harness.snapshot()

                    # Registrar ejecución en el historial de SQLite
                    bus.record_tool_execution(
                        tool_name=exec_result.get("tool_used", "none"),
                        task_id=task_id,
                        parameters=task,
                        output=exec_result.get("raw_results", {}),
                        success=response.status == MessageStatus.COMPLETED,
                    )

                    if response.status == MessageStatus.COMPLETED:
                        session.update_subtask(task_id, "done", exec_result)
                        completed_tasks.add(task_id)
                    else:
                        session.update_subtask(task_id, "failed", exec_result)

        session.agent_results["execution"] = results
        return results

    def _phase_evaluation(
        self,
        session: SessionState,
        bus: MessageBus,
        agents: dict,
        analysis: dict,
        plan: list[dict],
        execution_results: list[dict],
    ) -> dict:
        """
        FASE 4: Evaluación.
        El Evaluador verifica si el objetivo fue cumplido.
        """
        self._log.info("[PHASE] EVALUATION")
        self.state_manager.set_phase(session.session_id, TaskPhase.EVALUATION)

        msg = NexoMessage(
            from_agent=AgentID.ORCHESTRATOR,
            to_agent=AgentID.EVALUATOR,
            task_id=session.session_id,
            goal=session.goal,
            phase=TaskPhase.EVALUATION,
            payload={
                "analysis":          analysis,
                "plan":              plan,
                "execution_results": execution_results,
                "research": session.agent_results.get("research", {}),
                "quality_review": session.agent_results.get("quality_review", {}),
                "security_review": session.agent_results.get("security_review", {}),
            },
            context={
                "session_id":    session.session_id,
                "original_request": session.original_request,
            },
            status=MessageStatus.PENDING,
            next_action="EVALUATE",
            iteration=session.iteration,
        )
        bus.publish(msg)
        session.add_message(msg)

        response = agents["evaluator"].run()
        if response:
            session.add_message(response)
            evaluation = response.payload.get("evaluation", {})
            session.agent_results["evaluation"] = evaluation
            return evaluation

        return {"verdict": "REJECTED", "final_answer": "", "corrections_needed": []}

    def _run_aux_agent(self, session, bus, agent, key: str, phase: TaskPhase, payload: dict) -> dict:
        """Run a specialist through the same persisted Orchestrator message path."""
        message = NexoMessage(
            from_agent=AgentID.ORCHESTRATOR, to_agent=agent.agent_id,
            task_id=session.session_id, goal=session.original_request,
            phase=phase, payload=payload,
            context={"session_id": session.session_id,
                     "original_request": session.original_request,
                     "iteration": session.iteration},
            status=MessageStatus.PENDING, iteration=session.iteration,
        )
        bus.publish(message)
        session.add_message(message)
        response = agent.run()
        if not response:
            session.error_log.append(f"El agente {key} no produjo respuesta")
            return {}
        session.add_message(response)
        result = response.payload
        session.agent_results.setdefault("specialist_runs", []).append({
            "agent": agent.agent_id.value, "phase": phase.value,
            "status": response.status.value, "iteration": session.iteration,
        })
        return result

    def _run_coherence_check(self, session: SessionState, bus: MessageBus) -> dict:
        """
        Ejecuta el NCM sobre el estado actual de la sesión.
        """
        context = {
            "session_id": session.session_id,
            "messages":   session.messages,
            "plan":       session.plan,
            "goal":       session.goal,
            "iteration":  session.iteration,
        }
        result = self.coherence_monitor.execute(context)
        output = result.get("output", {})

        # Registrar evento de coherencia en SQLite
        bus.record_coherence_event(
            iteration=session.iteration,
            score=output.get("coherence_score", 1.0),
            anomalies=output.get("anomalies", []),
            recommendation=output.get("recommendation", ""),
        )

        self._log.info(
            "[NCM] Coherence=%.2f | Anomalies=%d | Replan=%s",
            output.get("coherence_score", 1.0),
            len(output.get("anomalies", [])),
            output.get("should_replan", False),
        )

        return output

    # ──────────────────────────────────────────────────────────────────
    # Utilidades
    # ──────────────────────────────────────────────────────────────────

    def _build_agents(self, bus: MessageBus) -> dict:
        """Construye los agentes con sus proveedores configurados."""
        def provider(role: str, fallback: str):
            selected = role if role in self.provider_config else fallback
            return build_provider(selected, self.provider_config)
        return {
            "analyst":    AnalystAgent(build_provider("ANALYST", self.provider_config), bus),
            "strategist": StrategistAgent(build_provider("STRATEGIST", self.provider_config), bus),
            "executor":   ExecutorAgent(build_provider("EXECUTOR", self.provider_config), bus, self.skill_registry),
            "evaluator":  EvaluatorAgent(build_provider("EVALUATOR", self.provider_config), bus),
            "researcher": ResearcherAgent(provider("RESEARCHER", "ANALYST"), bus),
            "qa": QAAgent(provider("QA", "EVALUATOR"), bus),
            "security": SecurityAgent(provider("SECURITY", "EVALUATOR"), bus),
        }

    def _load_memory_context(self, session: SessionState, agents: dict) -> str:
        """Recupera recuerdos solo en ejecución real; el modo mock evita I/O externo."""
        if all(isinstance(agent.provider, MockProvider) for agent in agents.values()):
            return ""
        try:
            from nexo.core.memory import buscar_en_memoria
            memory = buscar_en_memoria(session.original_request)
            self._log.info("Memory context loaded (%d chars)", len(memory))
            return memory
        except Exception as exc:
            self._log.warning("Memory retrieval failed; continuing without it: %s", exc)
            return ""

    def _remember_approved_result(self, session: SessionState, execution_results: list[dict]) -> None:
        """Persiste solo resultados aprobados para no contaminar la memoria con errores."""
        if session.agent_results.get("mock_mode"):
            self._log.info("Skipping memory write for mock-provider session")
            return
        try:
            from nexo.core.memory import guardar_en_memoria
            evaluation = session.agent_results.get("evaluation", {})
            guardar_en_memoria(
                f"Objetivo aprobado: {session.original_request}\n"
                f"Criterios: {evaluation.get('summary', '')}\n"
                f"Resultado verificado: {session.final_answer}\n"
                f"Ejecución: {execution_results}"
            )
        except Exception as exc:
            self._log.warning("Memory persistence failed: %s", exc)

    def _fail(self, session: SessionState, bus: MessageBus, reason: str) -> dict:
        session.status = SessionStatus.FAILED
        if self.harness:
            self.harness.finish("failed")
        session.error_log.append(reason)
        session.metrics.update({
            "end_time": time.time(),
            "iterations": session.iteration,
            "message_count": len(session.messages),
        })
        if self.harness:
            session.agent_results["harness"] = self.harness.snapshot()
            session.metrics["harness_tasks_started"] = session.agent_results["harness"].get("tasks_started", 0)
            session.metrics["harness_blocked_operations"] = session.agent_results["harness"].get("blocked_operations", 0)
        result = {
            **session.to_summary(),
            "status": "FAILED",
            "approved": False,
            "verdict": "FAILED",
            "final_answer": f"El sistema no pudo resolver la solicitud: {reason}",
            "error_log": list(session.error_log),
            "metrics": dict(session.metrics),
            "agent_results": dict(session.agent_results),
            "memory_context": session.agent_results.get("memory_context", ""),
            "messages": [m.to_dict() for m in session.messages],
            "plan": [
                {"id": task.task_id, "description": task.description,
                 "agent": task.assigned_to, "status": task.status,
                 "tool": task.tool_name, "skill": task.skill_name,
                 "permission": task.permission}
                for task in session.plan
            ],
        }
        bus.save_session(session.original_request, "FAILED", result)
        return result

    def _extract_best_answer(self, execution_results: list[dict]) -> str:
        """Extrae la mejor respuesta disponible de los resultados de ejecución."""
        for r in reversed(execution_results):
            result = r.get("result", {})
            if result.get("recommendation"):
                return result["recommendation"]
            if result.get("conclusion"):
                return result["conclusion"]
        return "No se pudo generar una respuesta definitiva."
