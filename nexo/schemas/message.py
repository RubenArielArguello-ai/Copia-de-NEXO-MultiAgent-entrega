"""
NEXO — Esquema de mensajes del protocolo de comunicación inter-agente.

Cada mensaje representa una unidad de comunicación estructurada entre agentes.
El protocolo garantiza trazabilidad, contexto y control de coherencia.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional
import uuid
from datetime import datetime, timezone


class AgentID(str, Enum):
    ORCHESTRATOR = "ORCHESTRATOR"
    ANALYST      = "ANALYST"
    STRATEGIST   = "STRATEGIST"
    EXECUTOR     = "EXECUTOR"
    EVALUATOR    = "EVALUATOR"
    USER         = "USER"
    SYSTEM       = "SYSTEM"


class MessageStatus(str, Enum):
    PENDING   = "PENDING"    # En cola, aún no procesado
    ACTIVE    = "ACTIVE"     # Siendo procesado
    COMPLETED = "COMPLETED"  # Completado con éxito
    PARTIAL   = "PARTIAL"    # Resultado incompleto pero utilizable
    FAILED    = "FAILED"     # Error en la ejecución
    BLOCKED   = "BLOCKED"    # Esperando dependencia


class TaskPhase(str, Enum):
    PERCEPTION   = "PERCEPTION"    # Recepción del problema
    ANALYSIS     = "ANALYSIS"      # Interpretación por el Analista
    PLANNING     = "PLANNING"      # Generación de plan por el Estratega
    EXECUTION    = "EXECUTION"     # Ejecución por el Ejecutor
    EVALUATION   = "EVALUATION"    # Verificación por el Evaluador
    CORRECTION   = "CORRECTION"    # Replanificación
    DELIVERY     = "DELIVERY"      # Entrega del resultado final


class CoherenceFlag(str, Enum):
    GOAL_DEVIATION      = "GOAL_DEVIATION"       # El agente se alejó del objetivo
    TASK_DUPLICATION    = "TASK_DUPLICATION"     # Subtarea duplicada detectada
    CONTRADICTION       = "CONTRADICTION"         # Resultado contradice hallazgo previo
    MISSING_DEPENDENCY  = "MISSING_DEPENDENCY"   # Dependencia requerida no satisfecha
    NEEDS_REPLAN        = "NEEDS_REPLAN"         # El plan debe revisarse


@dataclass
class NexoMessage:
    """
    Unidad de comunicación estructurada del protocolo NEXO.

    Cada intercambio entre agentes usa este formato para garantizar
    trazabilidad completa y soporte para el NEXO-Coherence Monitor.
    """
    from_agent:      AgentID
    to_agent:        AgentID
    task_id:         str
    goal:            str
    phase:           TaskPhase
    payload:         dict[str, Any]

    # Opcionales con defaults
    msg_id:          str               = field(default_factory=lambda: str(uuid.uuid4()))
    context:         dict[str, Any]    = field(default_factory=dict)
    evidence:        list[str]         = field(default_factory=list)
    status:          MessageStatus     = MessageStatus.PENDING
    next_action:     Optional[str]     = None
    coherence_flags: list[CoherenceFlag] = field(default_factory=list)
    timestamp:       str               = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    iteration:       int               = 0  # Número de ciclo de razonamiento

    def to_dict(self) -> dict:
        d = asdict(self)
        # Convertir enums a strings para serialización JSON
        d["from_agent"]      = self.from_agent.value
        d["to_agent"]        = self.to_agent.value
        d["phase"]           = self.phase.value
        d["status"]          = self.status.value
        d["coherence_flags"] = [f.value for f in self.coherence_flags]
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "NexoMessage":
        data = dict(data)
        data["from_agent"]      = AgentID(data["from_agent"])
        data["to_agent"]        = AgentID(data["to_agent"])
        data["phase"]           = TaskPhase(data["phase"])
        data["status"]          = MessageStatus(data["status"])
        data["coherence_flags"] = [CoherenceFlag(f) for f in data.get("coherence_flags", [])]
        return cls(**data)

    def reply(
        self,
        payload: dict[str, Any],
        status: MessageStatus = MessageStatus.COMPLETED,
        next_action: Optional[str] = None,
        evidence: Optional[list[str]] = None,
        coherence_flags: Optional[list[CoherenceFlag]] = None,
    ) -> "NexoMessage":
        """Genera un mensaje de respuesta a este mensaje."""
        return NexoMessage(
            from_agent=self.to_agent,
            to_agent=self.from_agent,
            task_id=self.task_id,
            goal=self.goal,
            phase=self.phase,
            payload=payload,
            context=self.context,
            evidence=evidence or [],
            status=status,
            next_action=next_action,
            coherence_flags=coherence_flags or [],
            iteration=self.iteration,
        )
