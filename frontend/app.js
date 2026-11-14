/**
 * NEXO — Frontend Dashboard JavaScript
 *
 * Gestiona:
 * - Envío de solicitudes al backend
 * - Polling del estado de la sesión
 * - Renderizado de agentes, mensajes, plan y coherence score
 * - Animaciones del ciclo cognitivo
 */

const API_BASE = window.location.origin;
const POLL_INTERVAL_MS = 2000;

async function apiFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = sessionStorage.getItem('nexo_api_token');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  let response = await fetch(url, { ...options, headers });
  if (response.status === 401 && !token) {
    const supplied = window.prompt('Esta instancia requiere API token. Se conservará solo en esta pestaña.');
    if (!supplied) return response;
    sessionStorage.setItem('nexo_api_token', supplied.trim());
    headers.set('Authorization', `Bearer ${supplied.trim()}`);
    response = await fetch(url, { ...options, headers });
  }
  return response;
}

// ── Estado local ────────────────────────────────────────────────────
let currentSessionId   = null;
let pollTimer          = null;
let renderedMessageIds = new Set();

// ── SVG gradient para el anillo NCM ─────────────────────────────────
// ── Iniciar sesión ───────────────────────────────────────────────────
async function startSession() {
  const input   = document.getElementById('request-input');
  const request = input.value.trim();

  if (!request) {
    input.focus();
    input.style.borderColor = '#f43f5e';
    setTimeout(() => input.style.borderColor = '', 1500);
    return;
  }

  // Reset UI
  resetUI();
  setSystemStatus('running', 'Iniciando sistema…');
  document.getElementById('run-btn').disabled = true;

  try {
    const res  = await apiFetch(`${API_BASE}/sessions`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ request }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Error al crear sesión');
    }

    const data = await res.json();
    currentSessionId = data.session_id;

    setSystemStatus('running', `Sesión ${currentSessionId.slice(0, 8)}…`);
    startPolling();
    poll();
    loadDashboardMetrics();
    loadHistory();

  } catch (err) {
    setSystemStatus('error', `Error: ${err.message}`);
    document.getElementById('run-btn').disabled = false;
  }
}

// ── Polling ──────────────────────────────────────────────────────────
function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(poll, POLL_INTERVAL_MS);
}

function stopPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = null;
}

async function poll() {
  if (!currentSessionId) return;

  try {
    // Obtener estado de la sesión
    const [sessionRes, messagesRes, coherenceRes, toolsRes, agentsRes] = await Promise.all([
      apiFetch(`${API_BASE}/sessions/${currentSessionId}`),
      apiFetch(`${API_BASE}/sessions/${currentSessionId}/messages`),
      apiFetch(`${API_BASE}/sessions/${currentSessionId}/coherence`),
      apiFetch(`${API_BASE}/sessions/${currentSessionId}/tools`),
      apiFetch(`${API_BASE}/agents/status?session_id=${encodeURIComponent(currentSessionId)}`)
    ]);

    if (!sessionRes.ok || !messagesRes.ok) return;

    const session  = await sessionRes.json();
    const messages = await messagesRes.json();
    const coherence = coherenceRes.ok ? await coherenceRes.json() : { coherence_events: [] };
    const tools = toolsRes.ok ? await toolsRes.json() : { tool_executions: [] };
    const agents = agentsRes.ok ? await agentsRes.json() : { agents: {} };

    updateUI(session, messages.messages || [], coherence.coherence_events || [], tools.tool_executions || [], agents.agents || {});

    if (['COMPLETED', 'FAILED', 'INTERRUPTED'].includes(session.status)) {
      stopPolling();
      setSystemStatus(
        session.status === 'COMPLETED' ? 'done' : 'error',
        session.status === 'INTERRUPTED' ? 'Interrumpida · reiniciar la misión' :
          session.status === 'COMPLETED'
            ? (session.approved ? 'Aprobado por el Evaluador' : 'Terminado sin aprobación')
            : 'Falló'
      );
      document.getElementById('run-btn').disabled = false;
      loadDashboardMetrics();
      loadHistory();
      loadLogs();
    }

  } catch (err) {
    console.error('Poll error:', err);
  }
}

function setSystemStatus(state, label) {
  const root = document.getElementById('system-status');
  if (!root) return;
  const dot = root.querySelector('.status-dot');
  if (dot) dot.className = `status-dot ${state}`;
  const text = document.getElementById('status-text');
  if (text) text.textContent = label;
}

function resetUI() {
  renderedMessageIds = new Set();
  const plan = document.getElementById('plan-tasks');
  if (plan) plan.innerHTML = '<div class="empty-state">Esperando el plan del Estratega…</div>';
  const messages = document.getElementById('messages-list');
  if (messages) messages.innerHTML = '<div class="empty-state">Esperando mensajes…</div>';
  const result = document.getElementById('result-panel');
  if (result) result.style.display = 'none';
  const evaluation = document.getElementById('evaluation-panel');
  if (evaluation) evaluation.style.display = 'none';
  const mission = document.getElementById('current-mission');
  if (mission) mission.textContent = 'Preparando la nueva misión…';
  document.getElementById('msg-count').textContent = '0 mensajes';
  document.getElementById('coherence-value').textContent = '—';
  document.getElementById('ring-score').textContent = '—';
  document.getElementById('ring-fill').style.strokeDashoffset = '213.6';
  document.getElementById('anomaly-count').textContent = '—';
  document.getElementById('anomaly-list').replaceChildren();
  const usedTools = document.getElementById('tools-used');
  if (usedTools) usedTools.replaceChildren();
  const memory = document.getElementById('memory-context');
  if (memory) memory.textContent = 'La memoria se mostrará para la misión seleccionada.';
  document.querySelectorAll('.phase-step').forEach((el) => el.classList.remove('active', 'complete'));
  document.querySelectorAll('.agent-status-dot').forEach((el) => { el.className = 'agent-status-dot idle'; });
  document.querySelectorAll('.agent-card').forEach((el) => el.classList.remove('active'));
  document.querySelectorAll('[data-flow]').forEach((el) => el.classList.remove('active'));
  const flowCaption = document.getElementById('flow-caption');
  if (flowCaption) flowCaption.textContent = 'Esperando una misión';
  const coordinator = document.getElementById('coordinator-status');
  if (coordinator) {
    coordinator.className = 'coordinator-indicator';
    coordinator.innerHTML = '<i class="status-dot"></i> Orquestador · esperando';
  }
}

function updateUI(session, messages, coherenceEvents = [], toolExecutions = [], agentStates = {}) {
  const phase = String(session.current_phase || '').toUpperCase();
  const phases = ['ANALYSIS', 'PLANNING', 'EXECUTION', 'EVALUATION', 'DELIVERY'];
  const terminal = session.status === 'COMPLETED';
  const currentIndex = terminal ? phases.length : phases.indexOf(phase);
  phases.forEach((name, index) => {
    const el = document.getElementById(`ph-${name}`);
    if (el) el.className = `phase-step ${index < currentIndex ? 'complete' : index === currentIndex ? 'active' : ''}`;
  });

  const plan = document.getElementById('plan-tasks');
  const tasks = session.plan_detail || [];
  plan.replaceChildren();
  if (!tasks.length) {
    plan.innerHTML = '<div class="empty-state">El Estratega todavía no generó tareas.</div>';
  } else {
    tasks.forEach((task) => {
      const row = document.createElement('article');
      row.className = `plan-task ${String(task.status || 'pending').toLowerCase()}`;
      const title = document.createElement('strong');
      title.textContent = `${task.id}: ${task.description}`;
      const meta = document.createElement('span');
      meta.textContent = `${task.agent} · ${task.status}${task.depends_on?.length ? ` · depende de ${task.depends_on.join(', ')}` : ''}`;
      row.append(title, meta);
      plan.append(row);
    });
  }

  const list = document.getElementById('messages-list');
  list.replaceChildren();
  if (!messages.length) {
    list.innerHTML = '<div class="empty-state">Todavía no hay mensajes inter-agente.</div>';
  } else {
    messages.forEach((message) => {
      const id = message.msg_id || message.id || `${message.from_agent}-${message.timestamp}`;
      renderedMessageIds.add(id);
      const card = document.createElement('article');
      card.className = 'message-card';
      const heading = document.createElement('strong');
      heading.textContent = `${message.from_agent || '?'} → ${message.to_agent || '?'} · ${message.phase || ''} · ${message.status || ''}`;
      const body = document.createElement('pre');
      body.textContent = summarizeMessage(message);
      const detail = document.createElement('details');
      const summary = document.createElement('summary');
      summary.textContent = 'Ver payload completo';
      const payload = document.createElement('pre');
      payload.textContent = JSON.stringify(message.payload || {}, null, 2);
      detail.append(summary, payload);
      card.append(heading, body, detail);
      list.append(card);
    });
  }
  document.getElementById('msg-count').textContent = `${messages.length} mensajes`;
  renderToolExecutions(toolExecutions);
  updateAgentStates(agentStates, messages);
  const objective = session.original_request || session.request || 'Objetivo no disponible';
  document.getElementById('current-mission').textContent = objective;
  const memoryContext = session.agent_results?.memory_context || session.memory_context || '';
  document.getElementById('memory-context').textContent = memoryContext || 'No había recuerdos relevantes o la memoria estaba vacía.';

  const latest = coherenceEvents[coherenceEvents.length - 1];
  const sessionScore = session.coherence_score == null ? Number.NaN : Number(session.coherence_score);
  const score = latest
    ? (latest.score == null ? Number.NaN : Number(latest.score))
    : Number(session.iteration) > 0 ? sessionScore : Number.NaN;
  if (Number.isFinite(score)) {
    document.getElementById('coherence-value').textContent = Number.isFinite(score) ? score.toFixed(2) : '—';
    const boundedScore = Math.max(0, Math.min(1, score));
    document.getElementById('ring-score').textContent = `${Math.round(boundedScore * 100)}%`;
    document.getElementById('ring-fill').style.strokeDashoffset = String(213.6 * (1 - boundedScore));
  } else {
    document.getElementById('coherence-value').textContent = '—';
    document.getElementById('ring-score').textContent = '—';
    document.getElementById('ring-fill').style.strokeDashoffset = '213.6';
  }
  if (latest) {
    let anomalies = latest.anomalies || [];
    if (typeof anomalies === 'string') {
      try { anomalies = JSON.parse(anomalies); } catch { anomalies = []; }
    }
    if (!Array.isArray(anomalies)) anomalies = [];
    document.getElementById('anomaly-count').textContent = String(anomalies.length);
    const anomalyList = document.getElementById('anomaly-list');
    anomalyList.replaceChildren();
    anomalies.forEach((item) => {
      const line = document.createElement('div');
      line.className = 'anomaly-item minor';
      line.textContent = `${item.flag || item.type || 'Anomalía'}: ${item.description || item.message || ''}`;
      anomalyList.append(line);
    });
  } else {
    document.getElementById('anomaly-count').textContent = '—';
    document.getElementById('anomaly-list').replaceChildren();
  }

  const result = document.getElementById('result-panel');
  if (['COMPLETED', 'FAILED', 'INTERRUPTED'].includes(session.status)) {
    result.style.display = '';
    result.dataset.approved = String(session.approved === true);
    const content = document.getElementById('result-content');
    content.replaceChildren();
    const verdict = document.createElement('strong');
    verdict.textContent = session.approved ? 'APROBADO' : `SIN APROBACIÓN (${session.verdict || 'N/A'})`;
    const answer = document.createElement('p');
    answer.textContent = session.final_answer || session.error_log?.join('\n') || 'La sesión no produjo respuesta.';
    content.append(verdict, answer);
    const metrics = session.metrics || {};
    document.getElementById('metrics-row').textContent =
      `Iteraciones: ${metrics.iterations ?? session.iteration ?? 0} · ` +
      `Replanificaciones: ${metrics.replan_count ?? 0} · ` +
      `Coherencia: ${Number.isFinite(Number(session.coherence_score)) ? Number(session.coherence_score).toFixed(2) : '—'} · ` +
      `Duración: ${metrics.elapsed_seconds == null ? '—' : `${metrics.elapsed_seconds}s`}`;
  } else {
    result.style.display = 'none';
  }

  renderEvaluation(session.agent_results?.evaluation, session);
}

function summarizeMessage(message) {
  const payload = message.payload || {};
  const parts = [];
  if (payload.analysis) parts.push(payload.analysis.interpretation || 'Análisis recibido.');
  if (payload.plan) parts.push(payload.plan.strategy || `${payload.plan.plan?.length || 0} tarea(s) propuestas.`);
  if (payload.execution_result) {
    const result = payload.execution_result;
    parts.push(`${result.tool_used || 'herramienta'} · ${result.conclusion || result.interpretation || 'ejecución registrada'}`);
  }
  if (payload.evaluation) {
    const evaluation = payload.evaluation;
    parts.push(`${evaluation.verdict || 'Veredicto pendiente'} · ${evaluation.summary || ''}`);
  }
  return parts.filter(Boolean).join('\n') || `Mensaje ${message.status || 'registrado'} en ${message.phase || 'la sesión'}.`;
}

function renderEvaluation(evaluation, session) {
  const panel = document.getElementById('evaluation-panel');
  if (!panel) return;
  if (!evaluation || !Object.keys(evaluation).length) {
    panel.style.display = 'none';
    return;
  }
  panel.style.display = '';
  const verdict = String(evaluation.verdict || session.verdict || 'PENDING').toUpperCase();
  const chip = document.getElementById('evaluation-confidence');
  const confidence = Number(evaluation.confidence);
  chip.textContent = `${verdict}${Number.isFinite(confidence) ? ` · confianza ${Math.round(confidence * 100)}%` : ''}`;
  chip.className = `verdict-chip ${verdict.toLowerCase()}`;
  document.getElementById('evaluation-summary').textContent = evaluation.summary || evaluation.final_answer || 'El evaluador no entregó un resumen.';
  renderList('evaluation-issues', evaluation.issues_found, 'No se registraron problemas.');
  renderList('evaluation-corrections', evaluation.corrections_needed, 'No se registraron correcciones.');
}

function renderList(id, values, emptyLabel) {
  const list = document.getElementById(id);
  list.replaceChildren();
  const items = Array.isArray(values) ? values : [];
  if (!items.length) {
    const item = document.createElement('li');
    item.className = 'empty-inline';
    item.textContent = emptyLabel;
    list.append(item);
    return;
  }
  items.forEach((value) => {
    const item = document.createElement('li');
    item.textContent = typeof value === 'object' ? value.description || JSON.stringify(value) : String(value);
    list.append(item);
  });
}

function updateAgentStates(agentStates, messages) {
  Object.entries(agentStates).forEach(([role, data]) => {
    const dot = document.getElementById(`dot-${role}`);
    const status = String(data.status || 'idle').toLowerCase();
    if (dot) dot.className = `agent-status-dot ${status}`;
    document.getElementById(`agent-${role}`)?.classList.toggle('active', ['working', 'running'].includes(status));
    const model = document.querySelector(`[data-agent="${role}"] .agent-model`);
    if (model && data.model) {
      model.textContent = data.model_source === 'session'
        ? `Usó: ${data.model}`
        : data.provider === 'internal'
          ? `Coordinación: ${data.model}`
          : `Config actual: ${data.model} · histórico sin dato`;
    }
  });
  const coordinator = document.getElementById('coordinator-status');
  const coordinatorState = String(agentStates.ORCHESTRATOR?.status || 'idle').toLowerCase();
  if (coordinator) {
    coordinator.className = `coordinator-indicator ${coordinatorState === 'replanning' ? 'running' : coordinatorState}`;
  coordinator.innerHTML = `<i class="status-dot"></i> Orquestador · ${coordinatorState === 'running' || coordinatorState === 'replanning' ? 'coordinando' : coordinatorState === 'completed' ? 'finalizado' : coordinatorState === 'failed' ? 'con error' : 'esperando'}`;
  }
  const roles = ['ANALYST', 'STRATEGIST', 'EXECUTOR', 'EVALUATOR'];
  roles.forEach((role) => document.querySelector(`[data-flow="${role}"]`)?.classList.remove('active'));
  const last = messages[messages.length - 1];
  const activeRole = last?.to_agent && roles.includes(last.to_agent) ? last.to_agent : last?.from_agent;
  if (activeRole) document.querySelector(`[data-flow="${activeRole}"]`)?.classList.add('active');
  const caption = document.getElementById('flow-caption');
  if (caption) caption.textContent = last
    ? `${last.from_agent} → ${last.to_agent} · ${last.phase} · ${last.status}`
    : 'Esperando una misión';
}

function renderToolExecutions(executions) {
  const container = document.getElementById('tools-used');
  if (!container) return;
  container.replaceChildren();
  if (!executions.length) {
    container.innerHTML = '<div class="empty-state">Todavía no se ejecutaron herramientas.</div>';
    return;
  }
  executions.forEach((item) => {
    const line = document.createElement('article');
    line.className = 'message-card';
    const title = document.createElement('strong');
    title.textContent = `${item.tool_name} · ${item.success ? 'correcta' : 'fallida'}`;
    const detail = document.createElement('pre');
    detail.textContent = `Tarea: ${item.task_id || '—'}\nDuración: ${item.duration_ms == null ? '—' : `${item.duration_ms} ms`}\nSalida: ${item.output || '—'}`;
    line.append(title, detail);
    container.append(line);
  });
}

async function loadModels() {
  try {
    const response = await apiFetch(`${API_BASE}/models`);
    if (!response.ok) return;
    const data = await response.json();
    const available = data.ollama_connected === true;
    const modelRoles = Object.entries(data.providers || {}).filter(([role]) => role !== 'ORCHESTRATOR');
    const installed = modelRoles.filter(([, info]) => info.available_in_ollama).length;
    const configured = modelRoles.length;
    const ollamaStatus = document.getElementById('ollama-status');
    if (ollamaStatus) {
      ollamaStatus.className = `ollama-indicator ${available ? 'online' : 'offline'}`;
      ollamaStatus.textContent = available
        ? `Ollama conectado · ${installed}/${configured} modelos`
        : 'Ollama desconectado';
    }
    Object.entries(data.providers || {}).forEach(([role, info]) => {
      const card = document.querySelector(`[data-agent="${role}"] .agent-model`);
      if (card) card.textContent = `Modelo: ${info.model} · ${info.available_in_ollama ? 'instalado' : 'no instalado'}`;
    });
  } catch (error) {
    console.warn('No se pudo consultar el estado de Ollama:', error);
  }
}

async function loadTools() {
  const container = document.getElementById('tools-list');
  if (!container) return;
  try {
    const response = await apiFetch(`${API_BASE}/tools`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    container.replaceChildren();
    (data.tools || []).forEach((tool) => {
      const line = document.createElement('article');
      line.className = 'plan-task';
      const name = document.createElement('strong');
      name.textContent = tool.name;
      const description = document.createElement('span');
      description.textContent = tool.description;
      line.append(name, description);
      container.append(line);
    });
    const skillsResponse = await apiFetch(`${API_BASE}/skills`);
    if (skillsResponse.ok) {
      const skillsData = await skillsResponse.json();
      const heading = document.createElement('h4');
      heading.textContent = 'Skills registradas';
      container.append(heading);
      (skillsData.skills || []).forEach((skill) => {
        const line = document.createElement('article');
        line.className = 'plan-task';
        const name = document.createElement('strong');
        name.textContent = `${skill.name} · v${skill.version}`;
        const description = document.createElement('span');
        description.textContent = `${skill.description} · ${skill.permission} · ${skill.tool}`;
        line.append(name, description);
        container.append(line);
      });
    }
  } catch (error) {
    container.textContent = `No se pudo cargar el registro: ${error.message}`;
  }
}

async function loadDashboardMetrics() {
  try {
    const response = await apiFetch(`${API_BASE}/dashboard/metrics`);
    if (!response.ok) return;
    const data = await response.json();
    document.getElementById('metric-missions').textContent = data.missions_total;
    document.getElementById('metric-active').textContent = data.sessions_active;
    document.getElementById('metric-approved').textContent = data.missions_approved;
    document.getElementById('metric-approval-rate').textContent = data.approval_rate == null ? '—' : `${(data.approval_rate * 100).toFixed(0)}%`;
    document.getElementById('metric-rejected').textContent = data.missions_rejected;
    document.getElementById('metric-failed').textContent = data.missions_failed;
    document.getElementById('metric-tasks').textContent = `${data.tasks_completed}/${data.tasks_total}`;
    document.getElementById('metric-duration').textContent = data.average_seconds_completed == null ? '—' : `${data.average_seconds_completed}s`;
    document.getElementById('metrics-provenance').textContent =
      `Últimas 1.000 sesiones de SQLite: ${data.missions_real} ejecuciones Ollama clasificadas · ${data.missions_mock} sesiones mock · ` +
      `${data.missions_unclassified} sesiones sin marca de proveedor. Aprobación (sobre reales completadas), tareas y duración usan solo ejecuciones reales clasificadas.`;
  } catch (error) {
    console.warn('No se pudieron cargar métricas:', error);
  }
}

async function loadHistory() {
  const container = document.getElementById('session-history');
  if (!container) return;
  try {
    const response = await apiFetch(`${API_BASE}/sessions`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    container.replaceChildren();
    if (!data.sessions?.length) {
      container.innerHTML = '<div class="empty-state">Todavía no hay misiones.</div>';
      return;
    }
    data.sessions.forEach((session) => {
      const button = document.createElement('button');
      button.className = `history-item ${session.session_id === currentSessionId ? 'selected' : ''}`;
      button.type = 'button';
      button.textContent = session.original_request || session.request || session.session_id;
      const meta = document.createElement('small');
      const verdict = session.verdict || (session.approved ? 'APPROVED' : 'PENDING');
      meta.textContent = `${session.status} · ${verdict} · ${session.session_id.slice(0, 8)}`;
      button.append(meta);
      button.addEventListener('click', () => {
        currentSessionId = session.session_id;
        setSystemStatus('idle', `Cargando ${currentSessionId.slice(0, 8)}…`);
        startPolling();
        poll();
        loadHistory();
      });
      container.append(button);
    });
  } catch (error) {
    container.textContent = `No se pudo cargar el historial: ${error.message}`;
  }
}

async function loadLogs() {
  const container = document.getElementById('system-logs');
  if (!container) return;
  try {
    const response = await apiFetch(`${API_BASE}/dashboard/logs?limit=40`);
    if (!response.ok) return;
    const data = await response.json();
    container.replaceChildren();
    if (!data.events?.length) {
      container.innerHTML = '<div class="empty-state">Sin eventos recientes.</div>';
      return;
    }
    data.events.slice(-30).reverse().forEach((event) => {
      const line = document.createElement('div');
      line.className = `log-entry ${event.level || 'INFO'}`;
      line.textContent = `${event.timestamp ? new Date(event.timestamp).toLocaleTimeString() + ' · ' : ''}${event.message}`;
      container.append(line);
    });
  } catch (error) {
    container.textContent = `No se pudieron cargar los eventos: ${error.message}`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadModels();
  setInterval(loadModels, 15000);
  loadTools();
  loadDashboardMetrics();
  loadHistory();
  loadLogs();
  setInterval(loadLogs, 10000);
});
