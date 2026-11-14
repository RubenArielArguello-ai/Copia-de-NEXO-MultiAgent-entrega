"""
NEXO — API REST con FastAPI.

Endpoints:
  POST   /sessions            → Crea una nueva sesión y ejecuta el sistema
  GET    /sessions            → Lista todas las sesiones
  GET    /sessions/{id}       → Estado detallado de una sesión
  GET    /sessions/{id}/messages → Historial de mensajes de la sesión
  GET    /health              → Health check del sistema
"""

from __future__ import annotations
import logging
import json
import os
import hmac
import time
from collections import defaultdict, deque
from statistics import mean
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pydantic import Field
from pathlib import Path

from nexo.core.orchestrator  import Orchestrator
from nexo.core.state_manager import StateManager
from nexo.core.message_bus   import MessageBus
from nexo.config import LOG_LEVEL, LOG_FORMAT

# ── Logging ───────────────────────────────────────────────────────────
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger("nexo.api")

# ── Estado global del servidor ────────────────────────────────────────
state_manager  = StateManager()
_running_tasks: dict[str, str] = {}  # session_id → "running"|"done"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("NEXO API iniciando...")
    yield
    logger.info("NEXO API cerrando.")


app = FastAPI(
    title="NEXO — Sistema Cognitivo Multiagente",
    description="API REST para el sistema multiagente NEXO",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("NEXO_CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",") if origin.strip()],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

_request_windows: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def protect_api(request: Request, call_next):
    """Optional bearer auth, bounded request size and simple per-client throttling."""
    if request.url.path == "/" or request.url.path.startswith("/static/") or request.method == "OPTIONS":
        pass
    else:
        token = os.getenv("NEXO_API_TOKEN", "").strip()
        if os.getenv("NEXO_ENV", "").lower() == "production" and not token:
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "API token requerido en producción"}, status_code=503)
        if token:
            supplied = request.headers.get("authorization", "")
            if not supplied.lower().startswith("bearer ") or not hmac.compare_digest(supplied[7:].strip(), token):
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail": "No autorizado"}, status_code=401)
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > 16_384:
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Solicitud demasiado grande"}, status_code=413)
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = _request_windows[client]
    while window and now - window[0] > 60:
        window.popleft()
    limit = 30 if request.method == "POST" else 300
    if len(window) >= limit:
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Límite de solicitudes excedido"}, status_code=429)
    window.append(now)
    return await call_next(request)

# Servir frontend estático
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Modelos Pydantic ──────────────────────────────────────────────────

class SessionRequest(BaseModel):
    request: str = Field(min_length=1, max_length=10_000)


class SessionResponse(BaseModel):
    session_id:  str
    status:      str
    message:     str


# ── Endpoints ─────────────────────────────────────────────────────────

@app.get("/")
async def root():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"name": "NEXO API", "version": "0.1.0", "docs": "/docs"}


@app.get("/health")
async def health():
    """Health check del sistema."""
    return {
        "status":    "ok",
        "sessions":  len(state_manager.list_sessions()),
    }


@app.post("/sessions", response_model=SessionResponse)
async def create_session(body: SessionRequest, background_tasks: BackgroundTasks):
    """
    Crea una nueva sesión y ejecuta el sistema multiagente en background.
    La ejecución es asíncrona: el endpoint devuelve inmediatamente
    con el session_id para que el cliente pueda hacer polling.
    """
    if not body.request or not body.request.strip():
        raise HTTPException(status_code=400, detail="La solicitud no puede estar vacía")

    session = state_manager.create_session(body.request.strip())
    _running_tasks[session.session_id] = "running"

    # Ejecutar en thread separado para no bloquear el event loop
    background_tasks.add_task(_run_session, session.session_id)

    logger.info("Session created: %s", session.session_id)
    return SessionResponse(
        session_id=session.session_id,
        status="CREATED",
        message="Sistema iniciado. Usá GET /sessions/{id} para ver el progreso.",
    )


@app.get("/sessions")
async def list_sessions():
    """Lista sesiones activas y el historial durable de SQLite."""
    records = MessageBus.list_session_records(limit=200)
    sessions = {item["session_id"]: item for item in state_manager.list_sessions()}
    for record in records:
        summary = record.get("summary") or {}
        summary.setdefault("session_id", record["session_id"])
        summary.setdefault("original_request", record["request"])
        summary.setdefault("status", record["status"])
        summary.setdefault("updated_at", record["updated_at"])
        session_id = record["session_id"]
        if session_id in sessions:
            # Une el resumen persistido (veredicto, agente, métricas) con el
            # estado vivo más reciente mantenido por StateManager.
            summary.update(sessions[session_id])
        elif summary.get("status") in {"RUNNING", "REPLANNING"} and session_id not in _running_tasks:
            summary["status"] = "INTERRUPTED"
        sessions[session_id] = summary
    return {"sessions": sorted(sessions.values(), key=lambda item: item.get("updated_at", ""), reverse=True)}


@app.get("/dashboard/metrics")
async def dashboard_metrics():
    """Métricas agregadas calculadas a partir del historial persistido."""
    records = MessageBus.list_session_records(limit=1000)
    summaries = [record.get("summary") or {} for record in records]
    statuses = [record.get("status", "UNKNOWN") for record in records]
    completed = sum(status == "COMPLETED" for status in statuses)
    provenance = [
        (summary.get("agent_results") or {}).get("mock_mode")
        for summary in summaries
    ]
    real_indexes = [i for i, is_mock in enumerate(provenance) if is_mock is False]
    mock_indexes = [i for i, is_mock in enumerate(provenance) if is_mock is True]
    unknown_indexes = [i for i, is_mock in enumerate(provenance) if is_mock is None]
    approved = sum(summaries[i].get("approved") is True for i in real_indexes)
    rejected = sum(
        statuses[i] == "COMPLETED" and summaries[i].get("approved") is False
        for i in real_indexes
    )
    # Solo estas sesiones pertenecen al proceso actual; registros RUNNING viejos
    # pueden quedar en SQLite tras un cierre inesperado y no son actividad viva.
    active = sum(status in {"running", "replanning"} for status in _running_tasks.values())
    elapsed = [
        float(summaries[i].get("metrics", {}).get("elapsed_seconds", 0))
        for i in real_indexes
        if statuses[i] == "COMPLETED"
        if summaries[i].get("metrics", {}).get("elapsed_seconds") is not None
    ]
    tasks = [task for i in real_indexes for task in summaries[i].get("plan", [])]
    real_completed = sum(statuses[i] == "COMPLETED" for i in real_indexes)
    return {
        "missions_total": len(records),
        "missions_real": len(real_indexes),
        "missions_mock": len(mock_indexes),
        "missions_unclassified": len(unknown_indexes),
        "missions_completed": completed,
        "missions_failed": sum(statuses[i] == "FAILED" for i in real_indexes),
        "missions_approved": approved,
        "missions_rejected": rejected,
        "sessions_active": active,
        "tasks_total": len(tasks),
        "tasks_completed": sum(task.get("status") == "done" for task in tasks),
        "approval_rate": round(approved / real_completed, 3) if real_completed else None,
        "average_seconds_completed": round(mean(elapsed), 2) if elapsed else None,
        # Campo anterior conservado para clientes REST que aún consumen este nombre.
        "average_seconds": round(mean(elapsed), 2) if elapsed else None,
    }


@app.get("/dashboard/logs")
async def dashboard_logs(limit: int = 50):
    """Eventos de mensajes y errores de las sesiones recientes."""
    events = []
    for record in MessageBus.list_session_records(limit=30):
        summary = record.get("summary") or {}
        for error in summary.get("error_log", []):
            events.append({"session_id": record["session_id"], "level": "ERROR", "message": error})
        bus = MessageBus(record["session_id"])
        for message in bus.get_session_messages(limit=20)[-10:]:
            events.append({
                "session_id": record["session_id"],
                "level": message.get("status", "INFO"),
                "message": f"{message.get('from_agent')} → {message.get('to_agent')} [{message.get('phase')}]",
                "timestamp": message.get("timestamp"),
            })
    return {"events": events[-max(1, min(limit, 200)): ]}


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """
    Devuelve el estado completo de una sesión.
    Incluye plan, resultados, métricas y coherence score.
    """
    session = state_manager.get_session(session_id)
    if not session:
        record = MessageBus(session_id).get_session_record()
        if not record:
            raise HTTPException(status_code=404, detail=f"Sesión {session_id} no encontrada")
        summary = record.get("summary") or {}
        summary.setdefault("session_id", session_id)
        summary.setdefault("original_request", record.get("request", ""))
        summary.setdefault("status", record.get("status", "UNKNOWN"))
        if summary["status"] in {"RUNNING", "REPLANNING"} and session_id not in _running_tasks:
            summary["status"] = "INTERRUPTED"
            summary.setdefault("error_log", []).append("Proceso detenido antes de persistir un estado terminal")
        summary.setdefault("verdict", "PENDING")
        summary.setdefault("approved", False)
        _restore_persisted_agent_results(summary, session_id)
        return summary

    summary = session.to_summary()
    summary["metrics"] = session.metrics
    summary["agent_results"] = session.agent_results
    evaluation = session.agent_results.get("evaluation", {})
    summary["verdict"] = evaluation.get("verdict", "PENDING")
    summary["approved"] = evaluation.get("verdict") == "APPROVED"
    summary["error_log"]     = session.error_log
    summary["plan_detail"]   = [
        {
            "id":          st.task_id,
            "description": st.description,
            "agent":       st.assigned_to,
            "status":      st.status,
            "depends_on":  st.depends_on,
        }
        for st in session.plan
    ]
    return summary


def _restore_persisted_agent_results(summary: dict, session_id: str) -> None:
    """Rearma los resultados visibles para sesiones guardadas con el formato anterior."""
    results = summary.get("agent_results")
    if not isinstance(results, dict):
        results = {}
        summary["agent_results"] = results
    if results.get("analysis") and results.get("evaluation"):
        return
    for message in MessageBus(session_id).get_session_messages(limit=1000):
        payload = message.get("payload") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                continue
        if not isinstance(payload, dict):
            continue
        role = message.get("from_agent")
        if role == "ANALYST" and payload.get("analysis"):
            results.setdefault("analysis", payload["analysis"])
        elif role == "STRATEGIST" and payload.get("plan"):
            results.setdefault("plan", payload["plan"])
        elif role == "EXECUTOR" and payload.get("execution_result"):
            if not results.get("execution"):
                results.setdefault("execution", []).append({"result": payload["execution_result"]})
        elif role == "EVALUATOR" and payload.get("evaluation"):
            results.setdefault("evaluation", payload["evaluation"])
    results.setdefault("memory_context", summary.get("memory_context", ""))
    if not summary.get("plan_detail"):
        summary["plan_detail"] = [
            {
                "id": item.get("id"),
                "description": item.get("description", ""),
                "agent": item.get("agent", "EXECUTOR"),
                "status": item.get("status", "pending"),
                "depends_on": item.get("depends_on", []),
            }
            for item in (summary.get("plan") if isinstance(summary.get("plan"), list) else [])
        ]


@app.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, limit: int = 100):
    """
    Devuelve el historial completo de mensajes inter-agente de la sesión.
    """
    session = state_manager.get_session(session_id)
    if not session:
        # Intentar desde SQLite si la sesión no está en memoria
        bus  = MessageBus(session_id)
        msgs = bus.get_session_messages(limit)
        if not msgs:
            raise HTTPException(status_code=404, detail=f"Sesión {session_id} no encontrada")
        return {"session_id": session_id, "messages": msgs}

    return {
        "session_id": session_id,
        "messages":   [m.to_dict() for m in session.messages[-limit:]],
        "total":      len(session.messages),
    }


@app.get("/sessions/{session_id}/tools")
async def get_session_tools(session_id: str):
    """Devuelve el registro de herramientas ejecutadas durante la sesión."""
    bus = MessageBus(session_id)
    tools = bus.get_session_tools()
    return {"session_id": session_id, "tool_executions": tools}


@app.get("/sessions/{session_id}/coherence")
async def get_session_coherence(session_id: str):
    """Devuelve el historial de evaluaciones del monitor NCM para la sesión."""
    bus = MessageBus(session_id)
    events = bus.get_session_coherence()
    return {"session_id": session_id, "coherence_events": events}


@app.get("/tools")
async def list_available_tools():
    """Lista las herramientas autorizadas y sus parámetros."""
    from nexo.tools.base_tool import ToolRegistry
    from nexo.tools.diagnostic_tool import NetworkDiagnosticTool
    from nexo.tools.system_tool import SystemDiagnosticTool
    from nexo.tools.port_tool import PortCheckTool
    from nexo.tools.basic_tools import FileReadTool, FileWriteTool

    reg = ToolRegistry()
    reg.register(NetworkDiagnosticTool())
    reg.register(SystemDiagnosticTool())
    reg.register(PortCheckTool())
    reg.register(FileReadTool())
    reg.register(FileWriteTool())
    return {"tools": reg.list_tools()}


@app.get("/skills")
async def list_available_skills():
    """Capabilities discoverable by the Orchestrator's executor."""
    from nexo.skills import SkillRegistry
    return {"skills": SkillRegistry().list_skills()}


@app.get("/models")
async def get_model_status():
    """Devuelve la configuración de modelos y disponibilidad de Ollama."""
    from nexo.config import PROVIDER_CONFIG, OLLAMA_BASE_URL
    from nexo.providers.base_provider import OllamaProvider

    models_info = {}
    availability_cache = {}
    server_cache = {}
    installed_models_cache = {}
    for role, cfg in PROVIDER_CONFIG.items():
        model_name = cfg.get("model", "")
        cache_key = (cfg.get("base_url", OLLAMA_BASE_URL), model_name)
        if cache_key[0] not in installed_models_cache:
            probe = OllamaProvider(model=model_name, base_url=cache_key[0])
            installed_models_cache[cache_key[0]] = probe.get_installed_models()
            server_cache[cache_key[0]] = installed_models_cache[cache_key[0]] is not None
        if cache_key not in availability_cache:
            availability_cache[cache_key] = OllamaProvider.model_is_installed(
                installed_models_cache[cache_key[0]] or [], model_name
            )
        models_info[role] = {
            "model": model_name,
            "type": cfg.get("type", "mock"),
            "available_in_ollama": availability_cache[cache_key],
        }
    return {
        "ollama_base_url": OLLAMA_BASE_URL,
        "ollama_connected": any(server_cache.values()),
        "models_installed": sum(availability_cache.values()),
        "providers": models_info,
    }


# ── Runner interno ────────────────────────────────────────────────────

def _run_session(session_id: str):
    """Ejecuta el orquestador en un thread separado."""
    try:
        orchestrator = Orchestrator(state_manager)
        result = orchestrator.run(session_id)
        _running_tasks[session_id] = result.get("status", "FAILED").lower()
        logger.info("Session %s completed", session_id[:8])
    except Exception as e:
        logger.error("Session %s failed: %s", session_id[:8], e, exc_info=True)
        _running_tasks[session_id] = "error"
        session = state_manager.get_session(session_id)
        if session:
            from nexo.core.state_manager import SessionStatus
            session.status = SessionStatus.FAILED
            session.error_log.append(str(e))


# Endpoints heredados conservados como alias del flujo actual.
@app.post("/start_mission")
async def start_mission(mission: str, background_tasks: BackgroundTasks):
    if not mission.strip():
        raise HTTPException(status_code=400, detail="La misión no puede estar vacía")
    session = state_manager.create_session(mission.strip())
    _running_tasks[session.session_id] = "running"
    background_tasks.add_task(_run_session, session.session_id)
    return {"status": "success", "session_id": session.session_id, "message": "Misión iniciada"}


@app.get("/agents/status")
async def get_agent_status(session_id: str | None = None):
    from nexo.config import PROVIDER_CONFIG
    from nexo.schemas.message import AgentID

    session = state_manager.get_session(session_id) if session_id else None
    persisted_session = MessageBus(session_id).get_session_record() if session_id and not session else None
    saved_summary = (persisted_session or {}).get("summary", {})
    models_used = (session.agent_results if session else saved_summary.get("agent_results", {})).get("models_used", {})
    messages = [message.to_dict() for message in session.messages] if session else []
    if session_id and not session:
        messages = MessageBus(session_id).get_session_messages(limit=500)
    agent_status = {}
    for agent in (AgentID.ANALYST, AgentID.STRATEGIST, AgentID.EXECUTOR, AgentID.EVALUATOR):
        status = "idle"
        for message in messages:
            if message.get("to_agent") == agent.value:
                status = "working" if message.get("status") == "PENDING" else str(message.get("status", "idle")).lower()
            if message.get("from_agent") == agent.value:
                status = str(message.get("status", "idle")).lower()
        config = PROVIDER_CONFIG[agent.value]
        model = models_used.get(agent.value)
        agent_status[agent.value] = {
            "status": status,
            "model": model or config["model"],
            "model_source": "session" if model else "current_config",
            "provider": config["type"],
        }
    saved_status = (persisted_session or {}).get("status", "idle")
    if saved_status in {"RUNNING", "REPLANNING"} and session_id not in _running_tasks:
        saved_status = "interrupted"
    agent_status["ORCHESTRATOR"] = {
        "status": session.status.value.lower() if session else str(saved_status).lower(),
        "model": "Python (coordinación determinista)",
        "provider": "internal",
    }
    return {
        "status": "ok",
        "agents": agent_status,
        "sessions": {key: value for key, value in _running_tasks.items()},
    }
