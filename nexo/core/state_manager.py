"""
NEXO — Gestión de sesiones y estado global de tareas.

El StateManager mantiene el estado completo de cada sesión:
- Historial de mensajes
- Plan actual
- Resultados de agentes
- Métricas de ejecución
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import uuid
from datetime import datetime, timezone

from nexo.schemas.message import NexoMessage, TaskPhase, MessageStatus


class SessionStatus(str, Enum):
    CREATED     = "CREATED"
    RUNNING     = "RUNNING"
    COMPLETED   = "COMPLETED"
    FAILED      = "FAILED"
    REPLANNING  = "REPLANNING"


@dataclass
class SubTask:
    """Representa una subtarea dentro del plan de resolución."""
    task_id:     str
    description: str
    assigned_to: str
    depends_on:  list[str] = field(default_factory=list)
    tool_name:  Optional[str] = None
    skill_name: Optional[str] = None
    permission: Optional[str] = None
    status:      str       = "pending"   # pending, active, done, failed
    result:      Any       = None
    created_at:  str       = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: Optional[str] = None


@dataclass
class SessionState:
    """Estado completo de una sesión de resolución de NEXO."""
    session_id:       str
    original_request: str
    goal:             str               = ""
    status:           SessionStatus     = SessionStatus.CREATED
    current_phase:    TaskPhase         = TaskPhase.PERCEPTION
    messages:         list[NexoMessage] = field(default_factory=list)
    plan:             list[SubTask]     = field(default_factory=list)
    agent_results:    dict[str, Any]    = field(default_factory=dict)
    coherence_score:  float             = 1.0   # 1.0 = perfecto, 0.0 = caótico
    iteration:        int               = 0
    max_iterations:   int               = 5
    final_answer:     Optional[str]     = None
    error_log:        list[str]         = field(default_factory=list)
    metrics:          dict[str, Any]    = field(default_factory=dict)
    created_at:       str               = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at:       str               = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def add_message(self, msg: NexoMessage) -> None:
        self.messages.append(msg)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def add_subtask(self, subtask: SubTask) -> None:
        self.plan.append(subtask)

    def update_subtask(self, task_id: str, status: str, result: Any = None) -> None:
        for st in self.plan:
            if st.task_id == task_id:
                st.status = status
                st.result = result
                if status in ("done", "failed"):
                    st.completed_at = datetime.now(timezone.utc).isoformat()
                break

    def get_pending_subtasks(self) -> list[SubTask]:
        return [st for st in self.plan if st.status == "pending"]

    def get_completed_subtasks(self) -> list[SubTask]:
        return [st for st in self.plan if st.status == "done"]

    def all_subtasks_done(self) -> bool:
        return all(st.status in ("done", "failed") for st in self.plan)

    def has_failed_subtasks(self) -> bool:
        return any(st.status == "failed" for st in self.plan)

    def messages_by_agent(self, agent_id: str) -> list[NexoMessage]:
        return [m for m in self.messages if m.from_agent.value == agent_id]

    def to_summary(self) -> dict:
        return {
            "session_id":       self.session_id,
            "original_request": self.original_request,
            "goal":             self.goal,
            "status":           self.status.value,
            "current_phase":    self.current_phase.value,
            "iteration":        self.iteration,
            "coherence_score":  round(self.coherence_score, 3),
            "plan_total":       len(self.plan),
            "plan_done":        len(self.get_completed_subtasks()),
            "message_count":    len(self.messages),
            "final_answer":     self.final_answer,
            "created_at":       self.created_at,
            "updated_at":       self.updated_at,
        }


class StateManager:
    """
    Gestiona el estado de todas las sesiones activas en memoria.
    La persistencia a SQLite se delega al SessionStore.
    """

    def __init__(self):
        self._sessions: dict[str, SessionState] = {}

    def create_session(self, request: str) -> SessionState:
        session_id = str(uuid.uuid4())
        session = SessionState(
            session_id=session_id,
            original_request=request,
            metrics={"start_time": datetime.now(timezone.utc).isoformat()}
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[SessionState]:
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[dict]:
        return [s.to_summary() for s in self._sessions.values()]

    def set_phase(self, session_id: str, phase: TaskPhase) -> None:
        s = self._sessions.get(session_id)
        if s:
            s.current_phase = phase
            s.updated_at = datetime.now(timezone.utc).isoformat()

    def increment_iteration(self, session_id: str) -> int:
        s = self._sessions.get(session_id)
        if s:
            s.iteration += 1
            return s.iteration
        return 0
