"""
NEXO — Bus de mensajes inter-agente y persistencia SQLite.

Gestiona el flujo de comunicación entre agentes mediante una cola
in-process, con persistencia asíncrona a SQLite para trazabilidad completa:
- Mensajes inter-agente
- Sesiones y estados
- Ejecuciones de herramientas auditadas
- Eventos de coherencia cognitiva (NCM)
"""

from __future__ import annotations
import json
import logging
import os
import sqlite3
from collections import deque
from pathlib import Path
from typing import Optional, Any
from datetime import datetime, timezone

from nexo.schemas.message import NexoMessage, AgentID

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("NEXO_DB_PATH", str(Path(__file__).parent.parent.parent / "nexo_data.db")))


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    """Inicializa el esquema SQLite completo si no existe."""
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                msg_id      TEXT NOT NULL UNIQUE,
                session_id  TEXT NOT NULL,
                from_agent  TEXT NOT NULL,
                to_agent    TEXT NOT NULL,
                phase       TEXT NOT NULL,
                status      TEXT NOT NULL,
                goal        TEXT,
                payload     TEXT,
                evidence    TEXT,
                flags       TEXT,
                next_action TEXT,
                iteration   INTEGER DEFAULT 0,
                timestamp   TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session
            ON messages(session_id)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id  TEXT PRIMARY KEY,
                request     TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'CREATED',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                summary     TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tool_executions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                tool_name   TEXT NOT NULL,
                task_id     TEXT,
                parameters  TEXT,
                output      TEXT,
                success     INTEGER NOT NULL,
                duration_ms REAL,
                timestamp   TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tools_session
            ON tool_executions(session_id)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coherence_events (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id     TEXT NOT NULL,
                iteration      INTEGER NOT NULL,
                score          REAL NOT NULL,
                anomalies      TEXT,
                recommendation TEXT,
                timestamp      TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_coherence_session
            ON coherence_events(session_id)
        """)
        conn.commit()


class MessageBus:
    """
    Bus de mensajes estructurado para comunicación inter-agente en NEXO.

    - Mantiene una cola in-process para procesamiento síncrono
    - Persiste cada mensaje en SQLite para trazabilidad
    - Registra ejecuciones de herramientas y eventos de coherencia
    - Permite consultar el historial completo de una sesión
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._queue: deque[NexoMessage] = deque()
        _init_db()

    def publish(self, msg: NexoMessage) -> None:
        """
        Publica un mensaje en el bus.
        Lo encola en memoria y lo persiste en SQLite.
        """
        self._queue.append(msg)
        self._persist(msg)
        logger.info(
            "[BUS] %s → %s | Phase: %s | Status: %s",
            msg.from_agent.value,
            msg.to_agent.value,
            msg.phase.value,
            msg.status.value,
        )

    def consume(self, to_agent: AgentID) -> Optional[NexoMessage]:
        """
        Consume el primer mensaje destinado a un agente específico.
        Devuelve None si no hay mensajes para ese agente.
        """
        for msg in list(self._queue):
            if msg.to_agent == to_agent and msg.status.value == "PENDING":
                self._queue.remove(msg)
                return msg
        return None

    def peek_all(self) -> list[NexoMessage]:
        """Devuelve todos los mensajes en cola sin consumirlos."""
        return list(self._queue)

    def _persist(self, msg: NexoMessage) -> None:
        """Guarda el mensaje en SQLite."""
        try:
            with _get_connection() as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO messages
                    (msg_id, session_id, from_agent, to_agent, phase, status,
                     goal, payload, evidence, flags, next_action, iteration, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    msg.msg_id,
                    self.session_id,
                    msg.from_agent.value,
                    msg.to_agent.value,
                    msg.phase.value,
                    msg.status.value,
                    msg.goal,
                    json.dumps(msg.payload),
                    json.dumps(msg.evidence),
                    json.dumps([f.value for f in msg.coherence_flags]),
                    msg.next_action,
                    msg.iteration,
                    msg.timestamp,
                ))
                conn.commit()
        except Exception as e:
            logger.error("Error persisting message %s: %s", msg.msg_id, e)

    def record_tool_execution(
        self,
        tool_name: str,
        task_id: Optional[str],
        parameters: dict[str, Any],
        output: dict[str, Any],
        success: bool,
        duration_ms: float = 0.0,
    ) -> None:
        """Registra la auditoría de ejecución de una herramienta en SQLite."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            with _get_connection() as conn:
                conn.execute("""
                    INSERT INTO tool_executions
                    (session_id, tool_name, task_id, parameters, output, success, duration_ms, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.session_id,
                    tool_name,
                    task_id,
                    json.dumps(parameters, default=str),
                    json.dumps(output, default=str),
                    1 if success else 0,
                    duration_ms,
                    now,
                ))
                conn.commit()
        except Exception as e:
            logger.error("Error recording tool execution: %s", e)

    def record_coherence_event(
        self,
        iteration: int,
        score: float,
        anomalies: list[dict[str, Any]],
        recommendation: str,
    ) -> None:
        """Registra un evento de evaluación del monitor NCM en SQLite."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            with _get_connection() as conn:
                conn.execute("""
                    INSERT INTO coherence_events
                    (session_id, iteration, score, anomalies, recommendation, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    self.session_id,
                    iteration,
                    score,
                    json.dumps(anomalies, default=str),
                    recommendation,
                    now,
                ))
                conn.commit()
        except Exception as e:
            logger.error("Error recording coherence event: %s", e)

    def get_session_messages(self, limit: int = 200) -> list[dict]:
        """Recupera el historial completo de mensajes de la sesión desde SQLite."""
        try:
            with _get_connection() as conn:
                rows = conn.execute("""
                    SELECT * FROM messages
                    WHERE session_id = ?
                    ORDER BY id ASC
                    LIMIT ?
                """, (self.session_id, limit)).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error("Error reading session messages: %s", e)
            return []

    def get_session_record(self) -> Optional[dict[str, Any]]:
        """Devuelve el registro y resumen persistido de la sesión, si existe."""
        try:
            with _get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM sessions WHERE session_id = ?", (self.session_id,)
                ).fetchone()
            if not row:
                return None
            record = dict(row)
            try:
                record["summary"] = json.loads(record.get("summary") or "{}")
            except json.JSONDecodeError:
                record["summary"] = {}
            return record
        except Exception as exc:
            logger.error("Error reading session record: %s", exc)
            return None

    @staticmethod
    def list_session_records(limit: int = 200) -> list[dict[str, Any]]:
        """Recupera historial persistente ordenado por última actualización."""
        try:
            with _get_connection() as conn:
                rows = conn.execute(
                    "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
                ).fetchall()
            records = []
            for row in rows:
                record = dict(row)
                try:
                    record["summary"] = json.loads(record.get("summary") or "{}")
                except json.JSONDecodeError:
                    record["summary"] = {}
                records.append(record)
            return records
        except Exception as exc:
            logger.error("Error reading session history: %s", exc)
            return []

    def get_session_tools(self) -> list[dict]:
        """Recupera el historial de herramientas ejecutadas en la sesión."""
        try:
            with _get_connection() as conn:
                rows = conn.execute("""
                    SELECT * FROM tool_executions
                    WHERE session_id = ?
                    ORDER BY id ASC
                """, (self.session_id,)).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error("Error reading session tools: %s", e)
            return []

    def get_session_coherence(self) -> list[dict]:
        """Recupera los eventos NCM de la sesión."""
        try:
            with _get_connection() as conn:
                rows = conn.execute("""
                    SELECT * FROM coherence_events
                    WHERE session_id = ?
                    ORDER BY id ASC
                """, (self.session_id,)).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error("Error reading session coherence events: %s", e)
            return []

    def save_session(self, request: str, status: str, summary: dict) -> None:
        """Registra o actualiza la sesión en SQLite."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            with _get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO sessions
                    (session_id, request, status, created_at, updated_at, summary)
                    VALUES (?, ?, ?, COALESCE(
                        (SELECT created_at FROM sessions WHERE session_id = ?), ?
                    ), ?, ?)
                """, (
                    self.session_id,
                    request,
                    status,
                    self.session_id, now,
                    now,
                    json.dumps(summary),
                ))
                conn.commit()
        except Exception as e:
            logger.error("Error saving session: %s", e)
