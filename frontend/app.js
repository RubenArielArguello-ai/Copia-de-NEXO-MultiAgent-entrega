/**
 * NEXO — Frontend Dashboard JavaScript
 *
 * Gestiona:
 * - Envío de solicitudes al backend
 * - Polling del estado de la sesión
 * - Renderizado de agentes, mensajes, plan y coherence score
 * - Animaciones del ciclo cognitivo
 */

const API_BASE = 'http://localhost:8000';
const POLL_INTERVAL_MS = 2000;

// ── Estado local ────────────────────────────────────────────────────
let currentSessionId   = null;
let pollTimer          = null;
let renderedMessageIds = new Set();

// ── SVG gradient para el anillo NCM ─────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Inyectar defs SVG globales para el gradiente del anillo
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.style.width = '0'; svg.style.height = '0'; svg.style.position = 'absolute';
  svg.innerHTML = `
    <defs>
      <linearGradient id="ring-grad" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%"   stop-color="#7c3aed"/>
        <stop offset="100%" stop-color="#06b6d4"/>
      </linearGradient>
    </defs>`;
  document.body.prepend(svg);
});

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
    const res  = await fetch(`${API_BASE}/sessions`, {
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
    const [sessionRes, messagesRes] = await Promise.all([
      fetch(`${API_BASE}/sessions/${currentSessionId}`),
      fetch(`${API_BASE}/sessions/${currentSessionId}/messages`),
    ]);

    if (!sessionRes.ok) return;

    const session  = await sessionRes.json();
    const messages = messagesRes.ok ? await messagesRes.json() : { messages: [] };

    updateUI(session, messages.messages || []);

    if (['COMPLETED', 'FAILED'].includes(session.status)) {
      stopPolling();
      setSystemStatus(
        session.status === 'COMPLETED' ? 'done' : 'error',
        session.status === 'COMPLETED' ? 'Completado' : 'Falló'
      );
      document.getElementById('run-btn').disabled = false;
    }

  } catch (err) {
    console.error('Poll error:', err);
  }
}

// ── Actualizar toda la UI ────────────────────────────────────────────
function updateUI(session, messages) {
  updatePhaseBar(session.current_phase);
  updateAgents(session.current_phase, messages);
  updatePlan(session.plan_detail || []);
  updateMessages(messages);
  updateCoherence(session, messages);

  if (session.final_answer) {
    showResult(session);
  }
}

// ── Phase Bar ────────────────────────────────────────────────────────
const PHASE_ORDER = ['ANALYSIS', 'PLANNING', 'EXECUTION', 'EVALUATION', 'DELIVERY'];

function updatePhaseBar(currentPhase) {
  const idx = PHASE_ORDER.indexOf(currentPhase);
  PHASE_ORDER.forEach((ph, i) => {
    const el = document.getElementById(`ph-${ph}`);
    if (!el) return;
    el.className = 'phase-step';
    if (i < idx)  el.classList.add('done');
    if (i === idx) el.classList.add('active');
  });
}

// ── Agents ───────────────────────────────────────────────────────────
const PHASE_TO_AGENT = {
  ANALYSIS:   'ANALYST',
  PLANNING:   'STRATEGIST',
  EXECUTION:  'EXECUTOR',
  EVALUATION: 'EVALUATOR',
  DELIVERY:   'ORCHESTRATOR',
};

function updateAgents(currentPhase, messages) {
  // Determinar qué agentes ya hablaron
  const agentsSpoken = new Set(messages.map(m => m.from_agent));

  ['ORCHESTRATOR', 'ANALYST', 'STRATEGIST', 'EXECUTOR', 'EVALUATOR'].forEach(agent => {
    const card = document.getElementById(`agent-${agent}`);
    const dot  = document.getElementById(`dot-${agent}`);
    if (!card || !dot) return;

    const isActive = PHASE_TO_AGENT[currentPhase] === agent || agent === 'ORCHESTRATOR';
    const hasDone  = agentsSpoken.has(agent);

    dot.className = 'agent-status-dot';
    card.classList.remove('active');

    if (isActive) {
      dot.classList.add('running');
      card.classList.add('active');
    } else if (hasDone) {
      dot.classList.add('done');
    } else {
      dot.classList.add('idle');
    }
  });
}

// ── Plan Tasks ───────────────────────────────────────────────────────
function updatePlan(planDetail) {
  const container = document.getElementById('plan-tasks');
  if (!planDetail || planDetail.length === 0) return;

  container.innerHTML = planDetail.map(task => {
    const icon = {
      pending: '○',
      active:  '◉',
      done:    '✓',
      failed:  '✗',
    }[task.status] || '○';

    return `
      <div class="task-item ${task.status}">
        <span class="task-id">${escHtml(task.id)}</span>
        <div>
          <div class="task-desc">${escHtml(task.description)}</div>
          <div class="task-agent">→ ${escHtml(task.agent)}</div>
        </div>
        <span class="task-status-icon">${icon}</span>
      </div>`;
  }).join('');
}

// ── Messages ─────────────────────────────────────────────────────────
function updateMessages(messages) {
  const container = document.getElementById('messages-list');
  const counter   = document.getElementById('msg-count');

  if (messages.length === 0) return;

  counter.textContent = `${messages.length} mensajes`;

  // Solo renderizar los nuevos
  const newMessages = messages.filter(m => !renderedMessageIds.has(m.msg_id));
  if (newMessages.length === 0) return;

  if (renderedMessageIds.size === 0) {
    container.innerHTML = '';  // limpiar empty-state
  }

  newMessages.forEach(msg => {
    renderedMessageIds.add(msg.msg_id);
    const el = buildMessageEl(msg);
    container.appendChild(el);
  });

  // Scroll al último
  container.scrollTop = container.scrollHeight;
}

function buildMessageEl(msg) {
  const payload = typeof msg.payload === 'string'
    ? JSON.parse(msg.payload || '{}')
    : msg.payload || {};

  // Preview: extraer texto relevante del payload
  const preview = extractPreview(payload);

  const el = document.createElement('div');
  el.className = 'msg-item';
  el.innerHTML = `
    <div class="msg-arrow">
      <span class="msg-from" data-agent="${escHtml(msg.from_agent)}">${escHtml(msg.from_agent)}</span>
      <span class="msg-sep">→</span>
      <span class="msg-to">${escHtml(msg.to_agent)}</span>
    </div>
    <div class="msg-body">
      <span class="msg-phase">${escHtml(msg.phase)}</span>
      <span class="msg-status ${escHtml(msg.status)}">${escHtml(msg.status)}</span>
      ${preview ? `<div class="msg-preview">${escHtml(preview)}</div>` : ''}
    </div>`;
  return el;
}

function extractPreview(payload) {
  if (!payload || typeof payload !== 'object') return '';

  // Buscar campos de texto en el payload
  const paths = [
    payload?.analysis?.interpretation,
    payload?.plan?.strategy,
    payload?.execution_result?.conclusion,
    payload?.execution_result?.recommendation,
    payload?.evaluation?.summary,
    payload?.evaluation?.final_answer,
    payload?.request,
  ];

  for (const v of paths) {
    if (v && typeof v === 'string' && v.length > 5) return v.slice(0, 150);
  }

  return '';
}

// ── Coherence Monitor ────────────────────────────────────────────────
function updateCoherence(session, messages) {
  const score = session.coherence_score;
  if (score === undefined || score === null) return;

  const scoreEl = document.getElementById('ring-score');
  const valueEl = document.getElementById('coherence-value');
  const countEl = document.getElementById('anomaly-count');
  const fill    = document.getElementById('ring-fill');

  scoreEl.textContent = `${Math.round(score * 100)}`;
  valueEl.textContent = score.toFixed(3);

  // Animar el anillo
  const circumference = 213.6;
  const offset        = circumference - (score * circumference);
  fill.style.strokeDashoffset = offset;
  fill.style.stroke = score >= 0.75 ? 'url(#ring-grad)'
    : score >= 0.5 ? '#f59e0b'
    : '#f43f5e';

  // Anomalías (placeholder; en producción vendrían de la API)
  const agentResults = session.agent_results || {};
  countEl.textContent = '—';

  // Si hay iteraciones de corrección, mostrar advertencia
  if (session.status === 'REPLANNING') {
    const listEl = document.getElementById('anomaly-list');
    listEl.innerHTML = `
      <div class="anomaly-item major">
        <span>⚠</span>
        <span>Replanificación en progreso (iteración ${session.iteration})</span>
      </div>`;
  }
}

// ── Result Panel ─────────────────────────────────────────────────────
function showResult(session) {
  const panel   = document.getElementById('result-panel');
  const content = document.getElementById('result-content');
  const metrics = document.getElementById('metrics-row');

  panel.style.display = 'block';
  content.textContent = session.final_answer || 'Sin respuesta disponible';

  const m = session.metrics || {};
  metrics.innerHTML = [
    m.elapsed_seconds && `<div class="metric-pill">⏱ <strong>${m.elapsed_seconds}s</strong></div>`,
    m.iterations      && `<div class="metric-pill">🔄 <strong>${m.iterations}</strong> iteraciones</div>`,
    m.replan_count !== undefined && `<div class="metric-pill">📋 <strong>${m.replan_count}</strong> replanificaciones</div>`,
    session.coherence_score !== undefined && `<div class="metric-pill">🧠 Score: <strong>${session.coherence_score?.toFixed(2)}</strong></div>`,
    m.message_count && `<div class="metric-pill">💬 <strong>${m.message_count}</strong> mensajes</div>`,
  ].filter(Boolean).join('');
}

// ── Status Header ─────────────────────────────────────────────────────
function setSystemStatus(state, text) {
  const dot  = document.querySelector('.status-dot');
  const label = document.getElementById('status-text');
  if (!dot || !label) return;
  dot.className   = `status-dot ${state}`;
  label.textContent = text;
}

// ── Reset UI ─────────────────────────────────────────────────────────
function resetUI() {
  currentSessionId   = null;
  renderedMessageIds = new Set();

  document.getElementById('plan-tasks').innerHTML =
    '<div class="empty-state">El plan aparecerá aquí una vez que el Estratega lo genere.</div>';
  document.getElementById('messages-list').innerHTML =
    '<div class="empty-state">Los mensajes entre agentes aparecerán aquí.</div>';
  document.getElementById('msg-count').textContent   = '0 mensajes';
  document.getElementById('result-panel').style.display = 'none';
  document.getElementById('anomaly-list').innerHTML  = '';
  document.getElementById('ring-score').textContent  = '—';
  document.getElementById('coherence-value').textContent = '—';
  document.getElementById('anomaly-count').textContent   = '—';

  const fill = document.getElementById('ring-fill');
  if (fill) fill.style.strokeDashoffset = '213.6';

  PHASE_ORDER.forEach(ph => {
    const el = document.getElementById(`ph-${ph}`);
    if (el) el.className = 'phase-step';
  });

  ['ORCHESTRATOR', 'ANALYST', 'STRATEGIST', 'EXECUTOR', 'EVALUATOR'].forEach(a => {
    const dot  = document.getElementById(`dot-${a}`);
    const card = document.getElementById(`agent-${a}`);
    if (dot)  dot.className  = 'agent-status-dot idle';
    if (card) card.classList.remove('active');
  });
}

// ── Utils ─────────────────────────────────────────────────────────────
function escHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Permitir enviar con Enter (Ctrl+Enter en textarea)
document.addEventListener('DOMContentLoaded', () => {
  const textarea = document.getElementById('request-input');
  if (textarea) {
    textarea.addEventListener('keydown', e => {
      if (e.key === 'Enter' && e.ctrlKey) {
        startSession();
      }
    });
  }
});
