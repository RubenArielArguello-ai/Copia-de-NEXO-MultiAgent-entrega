"""Mission execution guardrails shared by the Orchestrator and tools."""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any


class HarnessBlocked(RuntimeError):
    """Raised when a mission cannot continue within its runtime policy."""


class MissionHarness:
    """Cooperative mission deadline, emergency stop, task budget and audit trail."""

    def __init__(self, session_id: str, timeout_seconds: float = 300, max_tasks: int = 20):
        self.session_id = session_id
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self.max_tasks = max(1, int(max_tasks))
        self.started = time.monotonic()
        self.deadline = self.started + self.timeout_seconds
        self._events: list[dict[str, Any]] = []
        self._started_tasks = 0
        self._lock = threading.Lock()
        self._state = "active"

    def _emergency_stop(self) -> str | None:
        enabled = os.getenv("NEXO_EMERGENCY_STOP", "").strip().casefold()
        if enabled in {"1", "true", "yes", "on", "stop"}:
            return "Emergency stop enabled by NEXO_EMERGENCY_STOP"
        marker = os.getenv("NEXO_EMERGENCY_STOP_FILE", "").strip()
        if marker and Path(marker).is_file():
            return "Emergency stop marker is present"
        return None

    def check_active(self) -> None:
        stopped = self._emergency_stop()
        if stopped:
            self._state = "blocked"
            self._record("blocked", reason=stopped)
            raise HarnessBlocked(stopped)
        if time.monotonic() >= self.deadline:
            self._state = "timed_out"
            self._record("blocked", reason="Mission deadline exceeded")
            raise HarnessBlocked("Límite de duración de misión excedido")

    def finish(self, state: str = "completed") -> None:
        """Record the terminal mission state without changing its audit history."""
        if state not in {"completed", "failed", "interrupted"}:
            raise ValueError("Estado terminal inválido")
        with self._lock:
            if self._state == "active":
                self._state = state
        self._record("mission_finished", state=self._state)

    def begin_task(self, task_id: str, agent: str, tool: str) -> None:
        self.check_active()
        if agent != "EXECUTOR":
            self._record("blocked", task_id=task_id, agent=agent, tool=tool, reason="Agent is not authorized to execute tools")
            raise HarnessBlocked(f"Agente no autorizado para ejecutar herramientas: {agent}")
        with self._lock:
            over_budget = self._started_tasks >= self.max_tasks
            if not over_budget:
                self._started_tasks += 1
        if over_budget:
            self._state = "task_budget_exceeded"
            self._record("blocked", task_id=task_id, agent=agent, tool=tool, reason="Mission task budget exceeded")
            raise HarnessBlocked("Límite de ejecuciones de herramientas excedido")
        self._record("started", task_id=task_id, agent=agent, tool=tool)

    def finish_task(self, task_id: str, agent: str, tool: str, success: bool, duration_ms: float, skill_audit: dict | None = None, error: str | None = None) -> None:
        self._record("completed" if success else "failed", task_id=task_id, agent=agent,
                     tool=tool, duration_ms=round(float(duration_ms), 2),
                     permission=skill_audit, error=error)

    def _record(self, event: str, **fields) -> None:
        item = {"event": event, "elapsed_ms": round((time.monotonic() - self.started) * 1000, 2), **fields}
        with self._lock:
            self._events.append(item)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            events = list(self._events)
        return {
            "state": self._state,
            "session_id": self.session_id,
            "elapsed_seconds": round(time.monotonic() - self.started, 2),
            "timeout_seconds": self.timeout_seconds,
            "task_budget": self.max_tasks,
            "tasks_started": self._started_tasks,
            "tasks_completed": sum(e["event"] == "completed" for e in events),
            "tasks_failed": sum(e["event"] == "failed" for e in events),
            "blocked_operations": sum(e["event"] == "blocked" for e in events),
            "events": events,
        }
