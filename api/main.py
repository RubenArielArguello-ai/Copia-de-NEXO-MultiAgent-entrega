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
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
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
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir frontend estático
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Modelos Pydantic ──────────────────────────────────────────────────

class SessionRequest(BaseModel):
    request: str


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
    """Lista todas las sesiones con su estado."""
    return {"sessions": state_manager.list_sessions()}


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """
    Devuelve el estado completo de una sesión.
    Incluye plan, resultados, métricas y coherence score.
    """
    session = state_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Sesión {session_id} no encontrada")

    summary = session.to_summary()
    summary["agent_results"] = session.agent_results
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

    reg = ToolRegistry()
    reg.register(NetworkDiagnosticTool())
    reg.register(SystemDiagnosticTool())
    reg.register(PortCheckTool())
    return {"tools": reg.list_tools()}


@app.get("/models")
async def get_model_status():
    """Devuelve la configuración de modelos y disponibilidad de Ollama."""
    from nexo.config import PROVIDER_CONFIG, OLLAMA_BASE_URL
    from nexo.providers.base_provider import OllamaProvider

    models_info = {}
    for role, cfg in PROVIDER_CONFIG.items():
        if role == "default":
            continue
        model_name = cfg.get("model", "")
        prov = OllamaProvider(model=model_name, base_url=OLLAMA_BASE_URL)
        models_info[role] = {
            "model": model_name,
            "type": cfg.get("type", "mock"),
            "available_in_ollama": prov.is_available(),
        }
    return {
        "ollama_base_url": OLLAMA_BASE_URL,
        "providers": models_info,
    }


# ── Runner interno ────────────────────────────────────────────────────

def _run_session(session_id: str):
    """Ejecuta el orquestador en un thread separado."""
    try:
        orchestrator = Orchestrator(state_manager)
        orchestrator.run(session_id)
        _running_tasks[session_id] = "done"
        logger.info("Session %s completed", session_id[:8])
    except Exception as e:
        logger.error("Session %s failed: %s", session_id[:8], e, exc_info=True)
        _running_tasks[session_id] = "error"
