"""
NEXO-Coherence Monitor (NCM) — Herramienta propia de NEXO.

PROPÓSITO:
  Detectar anomalías cognitivas en la colaboración inter-agente
  analizando el grafo de mensajes en tiempo real.

CAPACIDADES (no cubiertas por LangSmith/Galileo/Phoenix):
  1. GOAL_DEVIATION:     El sistema trabaja en algo diferente al objetivo original
  2. TASK_DUPLICATION:   Dos subtareas son semánticamente equivalentes
  3. CONTRADICTION:      Un resultado contradice un hallazgo anterior
  4. MISSING_DEPENDENCY: Un agente usó resultados no disponibles
  5. CYCLE_RISK:         El sistema podría entrar en un ciclo infinito

TÉCNICA:
  - Similitud de Jaccard sobre tokens de las descripciones (sin GPU)
  - Análisis de dependencias sobre el grafo de mensajes
  - Detección de contradicción por palabras clave de polaridad opuesta
  - Circuit breaker para ciclos infinitos

SALIDA:
  - CoherenceScore [0.0 - 1.0]: 1.0 = perfecta coherencia
  - Lista de anomalías con severidad y descripción
  - Alertas al Orquestador para replanificación
"""

from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from nexo.schemas.message import NexoMessage, CoherenceFlag, TaskPhase
from nexo.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


# Pares de palabras con polaridad opuesta (para detección de contradicción)
CONTRADICTION_PAIRS = [
    ("success", "failure"), ("failed", "working"), ("up", "down"),
    ("activa", "inactiva"), ("funciona", "no funciona"), ("reachable", "unreachable"),
    ("conectado", "desconectado"), ("resuelto", "fallido"), ("ok", "error"),
    ("disponible", "no disponible"), ("aprobado", "rechazado"),
]


def _tokenize(text: str) -> set[str]:
    """Tokeniza texto en palabras normalizadas (sin stop words básicas)."""
    STOP = {"el", "la", "los", "las", "un", "una", "de", "del", "en", "y",
            "o", "a", "que", "se", "es", "son", "para", "con", "por", "the",
            "a", "an", "of", "in", "and", "or", "to", "is", "are", "for"}
    tokens = set(re.findall(r'\b[a-záéíóúña-z]{3,}\b', text.lower()))
    return tokens - STOP


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    """Similitud de Jaccard entre dos conjuntos de tokens."""
    if not a and not b:
        return 1.0
    intersection = len(a & b)
    union        = len(a | b)
    return intersection / union if union > 0 else 0.0


@dataclass
class CoherenceAnomaly:
    """Representa una anomalía detectada por el NCM."""
    flag:        CoherenceFlag
    severity:    str    # "critical" | "major" | "minor"
    description: str
    agents:      list[str] = field(default_factory=list)
    evidence:    str        = ""


@dataclass
class CoherenceReport:
    """Resultado completo de un análisis NCM."""
    session_id:        str
    score:             float               # 0.0 - 1.0
    anomalies:         list[CoherenceAnomaly] = field(default_factory=list)
    messages_analyzed: int                 = 0
    tasks_analyzed:    int                 = 0
    recommendation:    str                 = ""
    should_replan:     bool                = False
    cycle_risk:        bool                = False

    def to_dict(self) -> dict:
        return {
            "session_id":        self.session_id,
            "coherence_score":   round(self.score, 3),
            "anomalies":         [
                {
                    "flag":        a.flag.value,
                    "severity":    a.severity,
                    "description": a.description,
                    "agents":      a.agents,
                    "evidence":    a.evidence,
                }
                for a in self.anomalies
            ],
            "messages_analyzed": self.messages_analyzed,
            "tasks_analyzed":    self.tasks_analyzed,
            "recommendation":    self.recommendation,
            "should_replan":     self.should_replan,
            "cycle_risk":        self.cycle_risk,
        }


class CoherenceMonitor(BaseTool):
    """
    NEXO-Coherence Monitor (NCM).

    Analiza el grafo de mensajes de una sesión y detecta
    anomalías cognitivas que comprometen la calidad de la colaboración.
    """

    DUPLICATION_THRESHOLD  = 0.60  # Jaccard ≥ 0.60 → tarea duplicada (3 de 4 términos)
    DEVIATION_THRESHOLD    = 0.15  # Jaccard ≤ 0.15 → desviación del objetivo
    MAX_ITERATIONS_WARNING = 4     # Riesgo de ciclo si ≥ a este número

    @property
    def name(self) -> str:
        return "coherence_monitor"

    @property
    def description(self) -> str:
        return (
            "Detecta anomalías en la colaboración inter-agente: "
            "desviación del objetivo, tareas duplicadas, contradicciones "
            "y dependencias incumplidas"
        )

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Ejecuta el análisis NCM sobre el contexto de la sesión."""
        session_id = context.get("session_id", "unknown")
        messages   = context.get("messages", [])
        plan       = context.get("plan", [])
        goal       = context.get("goal", "")
        iteration  = context.get("iteration", 0)

        report = self.analyze(
            session_id=session_id,
            messages=messages,
            plan=plan,
            goal=goal,
            iteration=iteration,
        )

        return {
            "tool":    self.name,
            "output":  report.to_dict(),
            "success": True,
        }

    def analyze(
        self,
        session_id: str,
        messages: list[NexoMessage],
        plan: list[Any],
        goal: str,
        iteration: int = 0,
    ) -> CoherenceReport:
        """
        Análisis principal de coherencia.

        Detecta las 5 categorías de anomalías y calcula el CoherenceScore.
        """
        anomalies: list[CoherenceAnomaly] = []

        # ── 1. Detección de desviación del objetivo ───────────────────
        goal_anomalies = self._detect_goal_deviation(messages, goal)
        anomalies.extend(goal_anomalies)

        # ── 2. Detección de tareas duplicadas ─────────────────────────
        dup_anomalies = self._detect_task_duplication(plan)
        anomalies.extend(dup_anomalies)

        # ── 3. Detección de contradicciones ───────────────────────────
        contradiction_anomalies = self._detect_contradictions(messages)
        anomalies.extend(contradiction_anomalies)

        # ── 4. Dependencias incumplidas ───────────────────────────────
        dep_anomalies = self._detect_missing_dependencies(plan)
        anomalies.extend(dep_anomalies)

        # ── 5. Riesgo de ciclo infinito ───────────────────────────────
        cycle_risk = iteration >= self.MAX_ITERATIONS_WARNING

        # ── Cálculo del CoherenceScore ────────────────────────────────
        penalty_map = {"critical": 0.30, "major": 0.15, "minor": 0.05}
        total_penalty = sum(
            penalty_map.get(a.severity, 0.05) for a in anomalies
        )
        if cycle_risk:
            total_penalty += 0.20

        score = max(0.0, 1.0 - total_penalty)

        # ── Recomendación ─────────────────────────────────────────────
        should_replan = (
            any(a.severity == "critical" for a in anomalies) or
            score < 0.5 or
            cycle_risk
        )

        recommendation = self._build_recommendation(anomalies, score, cycle_risk)

        report = CoherenceReport(
            session_id=session_id,
            score=score,
            anomalies=anomalies,
            messages_analyzed=len(messages),
            tasks_analyzed=len(plan),
            recommendation=recommendation,
            should_replan=should_replan,
            cycle_risk=cycle_risk,
        )

        logger.info(
            "[NCM] Session %s | Score: %.2f | Anomalies: %d | Replan: %s",
            session_id[:8], score, len(anomalies), should_replan
        )

        return report

    # ──────────────────────────────────────────────────────────────────
    # Detectores individuales
    # ──────────────────────────────────────────────────────────────────

    def _detect_goal_deviation(
        self, messages: list[NexoMessage], goal: str
    ) -> list[CoherenceAnomaly]:
        """
        Detecta si los mensajes recientes se alejan semánticamente del objetivo.
        Analiza los últimos 3 mensajes con payload de texto.
        """
        anomalies = []
        goal_tokens = _tokenize(goal)
        if not goal_tokens:
            return anomalies

        recent = [m for m in messages[-5:] if m.payload]
        for msg in recent:
            payload_text = str(msg.payload)
            payload_tokens = _tokenize(payload_text)

            if len(payload_tokens) < 5:
                continue  # Payload muy corto, no analizable

            sim = _jaccard_similarity(goal_tokens, payload_tokens)
            if sim < self.DEVIATION_THRESHOLD:
                anomalies.append(CoherenceAnomaly(
                    flag=CoherenceFlag.GOAL_DEVIATION,
                    severity="major",
                    description=(
                        f"El mensaje de {msg.from_agent.value} tiene baja "
                        f"similitud con el objetivo (Jaccard={sim:.2f})"
                    ),
                    agents=[msg.from_agent.value],
                    evidence=f"Tokens comunes: {goal_tokens & payload_tokens}",
                ))
        return anomalies

    def _detect_task_duplication(self, plan: list[Any]) -> list[CoherenceAnomaly]:
        """
        Detecta tareas semánticamente equivalentes en el plan.
        """
        anomalies = []
        tasks = []

        for item in plan:
            if hasattr(item, "description"):
                tasks.append((item.task_id, item.description))
            elif isinstance(item, dict):
                tasks.append((item.get("id", "?"), item.get("task", "")))

        for i in range(len(tasks)):
            for j in range(i + 1, len(tasks)):
                id_a, desc_a = tasks[i]
                id_b, desc_b = tasks[j]
                tokens_a = _tokenize(desc_a)
                tokens_b = _tokenize(desc_b)
                sim = _jaccard_similarity(tokens_a, tokens_b)

                if sim >= self.DUPLICATION_THRESHOLD:
                    anomalies.append(CoherenceAnomaly(
                        flag=CoherenceFlag.TASK_DUPLICATION,
                        severity="major",
                        description=(
                            f"Tareas '{id_a}' y '{id_b}' son semánticamente "
                            f"similares (Jaccard={sim:.2f})"
                        ),
                        evidence=f"'{desc_a[:60]}' vs '{desc_b[:60]}'",
                    ))
        return anomalies

    def _detect_contradictions(self, messages: list[NexoMessage]) -> list[CoherenceAnomaly]:
        """
        Detecta cuando dos mensajes de agentes diferentes
        afirman cosas opuestas sobre el mismo tema.
        """
        anomalies = []
        texts = []

        for msg in messages:
            payload_str = str(msg.payload).lower()
            texts.append((msg.from_agent.value, payload_str))

        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                agent_a, text_a = texts[i]
                agent_b, text_b = texts[j]

                if agent_a == agent_b:
                    continue

                for pos, neg in CONTRADICTION_PAIRS:
                    if pos in text_a and neg in text_b:
                        anomalies.append(CoherenceAnomaly(
                            flag=CoherenceFlag.CONTRADICTION,
                            severity="critical",
                            description=(
                                f"{agent_a} afirma '{pos}' pero "
                                f"{agent_b} indica '{neg}'"
                            ),
                            agents=[agent_a, agent_b],
                            evidence=f"Par de contradicción: ({pos}, {neg})",
                        ))
                        break  # Un par es suficiente por par de agentes
        return anomalies

    def _detect_missing_dependencies(self, plan: list[Any]) -> list[CoherenceAnomaly]:
        """
        Verifica que todas las dependencias declaradas en el plan
        correspondan a tareas que existen.
        """
        anomalies = []
        task_ids = set()

        for item in plan:
            if hasattr(item, "task_id"):
                task_ids.add(item.task_id)
            elif isinstance(item, dict):
                task_ids.add(item.get("id", ""))

        for item in plan:
            if hasattr(item, "depends_on"):
                deps = item.depends_on
                current_id = item.task_id
            elif isinstance(item, dict):
                deps = item.get("depends_on", [])
                current_id = item.get("id", "?")
            else:
                continue

            for dep in deps:
                if dep not in task_ids:
                    anomalies.append(CoherenceAnomaly(
                        flag=CoherenceFlag.MISSING_DEPENDENCY,
                        severity="critical",
                        description=(
                            f"La tarea '{current_id}' depende de '{dep}' "
                            f"que no existe en el plan"
                        ),
                        evidence=f"Dependencia declarada: {dep}",
                    ))
        return anomalies

    def _build_recommendation(
        self,
        anomalies: list[CoherenceAnomaly],
        score: float,
        cycle_risk: bool,
    ) -> str:
        if not anomalies and not cycle_risk:
            return "Colaboración coherente. No se requieren acciones."

        parts = []
        flags = {a.flag for a in anomalies}

        if CoherenceFlag.GOAL_DEVIATION in flags:
            parts.append("Reorientar agentes hacia el objetivo original")
        if CoherenceFlag.TASK_DUPLICATION in flags:
            parts.append("Consolidar tareas duplicadas")
        if CoherenceFlag.CONTRADICTION in flags:
            parts.append("Resolver contradicción entre agentes antes de continuar")
        if CoherenceFlag.MISSING_DEPENDENCY in flags:
            parts.append("Corregir dependencias inválidas en el plan")
        if cycle_risk:
            parts.append("Forzar terminación o replanificación para evitar ciclo infinito")

        return " | ".join(parts) if parts else f"Score bajo ({score:.2f}): revisar coherencia general"
