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
    const res  = await fetch(`${API_BASE}/start_session`, {
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
      fetch(`${API_BASE}/session/${currentSessionId}`),
      fetch(`${API_BASE}/messages/${currentSessionId}`)
    ]);

    if (!sessionRes.ok || !messagesRes.ok) return;

    const session  = await sessionRes.json();
    const messages = await messagesRes.json();

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
