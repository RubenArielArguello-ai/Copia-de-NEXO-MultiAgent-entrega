"""Cliente Streamlit del Dashboard FastAPI de NEXO.

La API es la única ruta de ejecución y fuente de configuración de modelos.
El frontend web existente permanece servido por FastAPI en `/`.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

import streamlit as st

API_URL = os.getenv("NEXO_API_URL", "http://127.0.0.1:8000").rstrip("/")


def api(path: str, method: str = "GET", payload: dict | None = None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{API_URL}{path}", data=body, method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


st.set_page_config(page_title="NEXO MultiAgent", page_icon="🤖", layout="wide")
st.title("NEXO · Sistema Multiagente")
st.caption(f"Dashboard conectado a FastAPI · {API_URL}")

try:
    health = api("/health")
    models_data = api("/models")
    agents_data = api("/agents/status")
except Exception as exc:
    st.error(f"No se puede conectar con la API NEXO: {exc}")
    st.info("Iniciá FastAPI con `uvicorn api.main:app --reload` y actualizá esta página.")
    st.stop()

st.subheader("Agentes y modelos")
responsibilities = {
    "ANALYST": "Interpreta la solicitud y fija criterios verificables.",
    "STRATEGIST": "Convierte el análisis en tareas y dependencias.",
    "EXECUTOR": "Ejecuta herramientas y conserva evidencia observada.",
    "EVALUATOR": "Contrasta resultados con el objetivo y emite veredicto.",
}
agent_items = [(role, details) for role, details in agents_data.get("agents", {}).items() if role in responsibilities]
cols = st.columns(4)
agent_state_slots = {}
for col, (role, details) in zip(cols, agent_items):
    online = models_data.get("providers", {}).get(role, {}).get("available_in_ollama", False)
    with col.container(border=True):
        st.markdown(f"**{role.title()}**")
        st.caption(responsibilities[role])
        st.code(f"Configurado: {details.get('model', '—')}", language=None)
        st.caption("Modelo instalado" if online else "Modelo no disponible")
        agent_state_slots[role] = st.empty()
        agent_state_slots[role].caption(f"Estado: {details.get('status', 'idle')}")
coordinator = agents_data.get("agents", {}).get("ORCHESTRATOR", {})
api_state = "conectada" if health.get("status") == "ok" else "sin respuesta"
ollama_state = "conectado" if models_data.get("ollama_connected") else "desconectado"
coordinator_slot = st.empty()
coordinator_slot.caption(f"API {api_state} · Orquestador {coordinator.get('status', 'idle')} · Ollama {ollama_state} · {models_data.get('ollama_base_url')}")

try:
    dashboard_metrics = api("/dashboard/metrics")
    metric_cols = st.columns(8)
    metric_cols[0].metric("Misiones", dashboard_metrics.get("missions_total", "—"))
    metric_cols[1].metric("Activas", dashboard_metrics.get("sessions_active", "—"))
    metric_cols[2].metric("Aprobadas", dashboard_metrics.get("missions_approved", "—"))
    rate = dashboard_metrics.get("approval_rate")
    metric_cols[3].metric("Tasa aprobación", f"{rate * 100:.0f}%" if rate is not None else "—")
    metric_cols[4].metric("Rechazadas", dashboard_metrics.get("missions_rejected", "—"))
    metric_cols[5].metric("Fallos técnicos", dashboard_metrics.get("missions_failed", "—"))
    metric_cols[6].metric("Tareas completas", f"{dashboard_metrics.get('tasks_completed', 0)}/{dashboard_metrics.get('tasks_total', 0)}")
    duration = dashboard_metrics.get("average_seconds_completed")
    metric_cols[7].metric("Promedio", f"{duration}s" if duration is not None else "—")
    st.caption(f"Últimas 1.000 sesiones de SQLite: {dashboard_metrics.get('missions_real', 0)} ejecuciones Ollama clasificadas · {dashboard_metrics.get('missions_mock', 0)} sesiones mock · {dashboard_metrics.get('missions_unclassified', 0)} sesiones sin marca de proveedor. La tasa usa reales completadas; tareas y duración usan solo ejecuciones reales clasificadas.")
except Exception as exc:
    st.warning(f"No se pudieron leer las métricas: {exc}")

with st.form("mission"):
    objective = st.text_area("Objetivo de la misión", placeholder="Crea un archivo y luego léelo para verificarlo.")
    submitted = st.form_submit_button("Iniciar misión", type="primary")

if submitted:
    if not objective.strip():
        st.warning("Escribí un objetivo antes de iniciar.")
    else:
        try:
            created = api("/sessions", "POST", {"request": objective.strip()})
            st.session_state["nexo_session"] = created["session_id"]
        except Exception as exc:
            st.error(f"No se pudo iniciar la misión: {exc}")

session_id = st.session_state.get("nexo_session")
if session_id:
    status_box = st.empty()
    progress = st.progress(0)
    session = {}
    phase_progress = {"PERCEPTION": 0.08, "ANALYSIS": 0.2, "PLANNING": 0.4, "EXECUTION": 0.62, "EVALUATION": 0.82, "DELIVERY": 0.95}
    for tick in range(180):
        try:
            session = api(f"/sessions/{session_id}")
            current_agents = api(f"/agents/status?session_id={session_id}").get("agents", {})
            for role, slot in agent_state_slots.items():
                state = current_agents.get(role, {})
                model_label = "Usó" if state.get("model_source") == "session" else "Config actual; modelo histórico no registrado"
                slot.caption(f"Estado: {state.get('status', 'idle')} · {model_label}: {state.get('model', '—')}")
            coordinator_state = current_agents.get("ORCHESTRATOR", {}).get("status", "idle")
            coordinator_slot.caption(f"API {api_state} · Orquestador {coordinator_state} · Ollama {ollama_state} · {models_data.get('ollama_base_url')}")
            status = session.get("status", "UNKNOWN")
            status_box.info(f"Misión {session_id[:8]} · {status} · fase {session.get('current_phase', '—')}")
            if status in {"COMPLETED", "FAILED", "INTERRUPTED"}:
                progress.progress(100)
                break
            progress.progress(phase_progress.get(str(session.get("current_phase", "")).upper(), min(0.9, tick / 200)))
            time.sleep(1)
        except Exception as exc:
            status_box.error(f"Error consultando el progreso: {exc}")
            break
    st.subheader("Resultado")
    st.write(session.get("final_answer", "La misión sigue en ejecución."))
    st.json({"estado": session.get("status"), "veredicto": session.get("verdict"), "aprobado": session.get("approved"), "métricas": session.get("metrics", {}), "plan": session.get("plan_detail", [])})
    agent_results = session.get("agent_results", {})
    evaluation = agent_results.get("evaluation", {})
    if evaluation:
        st.subheader("Evaluación")
        st.write(evaluation.get("summary", "Sin resumen del Evaluador."))
        st.caption(f"Veredicto: {evaluation.get('verdict', '—')} · Confianza: {evaluation.get('confidence', '—')}")
        st.json({"problemas": evaluation.get("issues_found", []), "correcciones": evaluation.get("corrections_needed", [])})
    st.subheader("Memoria recuperada")
    st.write(agent_results.get("memory_context") or "La API no devolvió recuerdos para esta misión.")
    try:
        messages = api(f"/sessions/{session_id}/messages")
        tools = api(f"/sessions/{session_id}/tools")
        with st.expander("Mensajes y trazabilidad"):
            st.json(messages.get("messages", []))
        with st.expander("Herramientas ejecutadas"):
            st.json(tools.get("tool_executions", []))
        with st.expander("Errores y registros recientes"):
            st.json(api("/dashboard/logs?limit=30").get("events", []))
    except Exception as exc:
        st.warning(f"No se pudo cargar la trazabilidad: {exc}")

st.subheader("Historial de ejecuciones")
try:
    history = api("/sessions").get("sessions", [])
    st.dataframe([{"sesión": item.get("session_id", "")[:8], "estado": item.get("status"), "objetivo": item.get("original_request", ""), "actualizado": item.get("updated_at", "")} for item in history], use_container_width=True, hide_index=True)
    with st.expander("Herramientas disponibles"):
        st.json(api("/tools").get("tools", []))
except Exception as exc:
    st.warning(f"No se pudo cargar el historial: {exc}")
