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
from nexo.tools.coherence_monitor import CoherenceMonitor
from nexo.schemas.message import (
    NexoMessage, AgentID, MessageStatus, TaskPhase, CoherenceFlag
)
from nexo.providers.base_provider import build_provider
from nexo.config import PROVIDER_CONFIG, ORCHESTRATOR_CONFIG

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Orquestador central de NEXO.

    Gestiona el ciclo completo de resolución de una solicitud,
    coordinando los 4 agentes especializados.
    """

    def __init__(self, state_manager: StateManager):
        self.state_manager     = state_manager
        self.coherence_monitor = CoherenceMonitor()
        self.max_iterations    = ORCHESTRATOR_CONFIG["max_iterations"]
        self.max_replanning    = ORCHESTRATOR_CONFIG["max_replanning_cycles"]
        self.coherence_thr     = ORCHESTRATOR_CONFIG["coherence_threshold"]
        self._log              = logging.getLogger("nexo.orchestrator")

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

        self._log.info("=== NEXO SESSION START [%s] ===", session_id[:8])
        self._log.info("Request: %.100s", session.original_request)

        # Inicializar bus de mensajes para esta sesión
        bus = MessageBus(session_id)
        bus.save_session(session.original_request, "RUNNING", session.to_summary())

        # Construir agentes con sus proveedores
        agents = self._build_agents(bus)

        session.status = SessionStatus.RUNNING

        try:
            # ── FASE 1: PERCEPCIÓN + ANÁLISIS ─────────────────────────
            analysis = self._phase_analysis(session, bus, agents)
            if not analysis:
                return self._fail(session, bus, "El Analista no pudo interpretar la solicitud")

            # ── FASE 2: PLANIFICACIÓN ─────────────────────────────────
            plan = self._phase_planning(session, bus, agents, analysis)
            if not plan:
                return self._fail(session, bus, "El Estratega no pudo generar un plan")

            # ── CICLO: EJECUCIÓN + EVALUACIÓN + CORRECCIÓN ────────────
            while session.iteration < self.max_iterations:
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

        # ── Métricas finales ──────────────────────────────────────────
        elapsed = time.time() - start_time
        session.metrics.update({
            "end_time":       time.time(),
            "elapsed_seconds": round(elapsed, 2),
            "iterations":     session.iteration,
            "replan_count":   replan_count,
            "coherence_score": session.coherence_score,
            "message_count":  len(session.messages),
        })

        self._log.info(
            "=== SESSION COMPLETE [%s] | %.2fs | iter=%d | score=%.2f ===",
            session_id[:8], elapsed, session.iteration, session.coherence_score
        )

        result = {
            "session_id":     session_id,
            "status":         session.status.value,
            "final_answer":   session.final_answer,
            "coherence_score": session.coherence_score,
            "metrics":        session.metrics,
            "messages":       [m.to_dict() for m in session.messages],
            "plan":           [
                {
                    "id":          st.task_id,
                    "description": st.description,
                    "agent":       st.assigned_to,
                    "status":      st.status,
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
            context={"session_id": session.session_id},
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
            tasks     = plan_data.get("plan", [])

            # Registrar el plan en el estado de sesión
            session.plan.clear()
            for task in tasks:
                session.add_subtask(SubTask(
                    task_id=task.get("id", "T?"),
                    description=task.get("task", ""),
                    assigned_to=task.get("agent", "EXECUTOR"),
                    depends_on=task.get("depends_on", []),
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

        for task in plan:
            task_id  = task.get("id", "?")
            agent    = task.get("agent", "EXECUTOR")
            deps     = task.get("depends_on", [])

            # Verificar dependencias
            if not all(dep in completed_tasks for dep in deps):
                self._log.warning("Task %s skipped: unmet dependencies %s", task_id, deps)
                session.update_subtask(task_id, "failed", {"error": "dependencia no satisfecha"})
                continue

            if agent == "EXECUTOR":
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
        return {
            "analyst":    AnalystAgent(build_provider("ANALYST", PROVIDER_CONFIG), bus),
            "strategist": StrategistAgent(build_provider("STRATEGIST", PROVIDER_CONFIG), bus),
            "executor":   ExecutorAgent(build_provider("EXECUTOR", PROVIDER_CONFIG), bus),
            "evaluator":  EvaluatorAgent(build_provider("EVALUATOR", PROVIDER_CONFIG), bus),
        }

    def _fail(self, session: SessionState, bus: MessageBus, reason: str) -> dict:
        session.status = SessionStatus.FAILED
        session.error_log.append(reason)
        bus.save_session(session.original_request, "FAILED", session.to_summary())
        return {
            "session_id":   session.session_id,
            "status":       "FAILED",
            "final_answer": f"El sistema no pudo resolver la solicitud: {reason}",
            "metrics":      session.metrics,
            "messages":     [m.to_dict() for m in session.messages],
        }

    def _extract_best_answer(self, execution_results: list[dict]) -> str:
        """Extrae la mejor respuesta disponible de los resultados de ejecución."""
        for r in reversed(execution_results):
            result = r.get("result", {})
            if result.get("recommendation"):
                return result["recommendation"]
            if result.get("conclusion"):
                return result["conclusion"]
        return "No se pudo generar una respuesta definitiva."
