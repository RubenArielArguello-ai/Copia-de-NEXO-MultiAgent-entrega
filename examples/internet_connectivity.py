"""
NEXO — Demo de ejecución en consola.

Ejecuta el caso de estudio: "Mi computadora no se conecta a Internet"
mostrando el ciclo cognitivo completo de 10 etapas en la terminal.

Uso:
    python examples/internet_connectivity.py
    # O forzar modo mock (sin conexión a Ollama):
    python examples/internet_connectivity.py --mock
"""

import sys
import os
import logging
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

if "--mock" in sys.argv:
    os.environ["NEXO_PROVIDER_TYPE"] = "mock"

from nexo.core.orchestrator  import Orchestrator
from nexo.core.state_manager import StateManager
from nexo.core.message_bus   import MessageBus
from nexo.config             import LOG_LEVEL, PROVIDER_CONFIG

# Configurar logging legible para demo
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(name)-20s] %(message)s",
    datefmt="%H:%M:%S",
)

DEMO_REQUEST = (
    "Mi computadora no se conecta a Internet. "
    "El WiFi aparece como conectado pero no puedo abrir ninguna página web. "
    "El problema empezó esta mañana sin que yo hiciera ningún cambio."
)

SEPARATOR = "═" * 70


def print_banner():
    print(f"\n{SEPARATOR}")
    print("  NEXO — Sistema Cognitivo Multiagente")
    print("  Demo: Diagnóstico de Conectividad a Internet (10 Etapas)")
    print(SEPARATOR)


def print_section(title: str):
    print(f"\n{'─' * 70}")
    print(f"  {title}")
    print('─' * 70)


def run_demo():
    print_banner()

    # Detectar argumentos personalizados de solicitud
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    request = " ".join(args) if args else DEMO_REQUEST

    print(f"\n📋 Solicitud:\n   {request}\n")

    # Inicializar sistema
    state_manager = StateManager()
    session       = state_manager.create_session(request)

    print(f"🆔 Sesión: {session.session_id}")
    print(f"⚙️ Proveedor preferido: {PROVIDER_CONFIG.get('ANALYST', {}).get('type', 'ollama').upper()}")
    print(f"\n▶ Iniciando ciclo cognitivo (10 etapas)...\n")

    # Ejecutar Orquestador
    orchestrator = Orchestrator(state_manager)
    result       = orchestrator.run(session.session_id)

    # ── Mostrar resultados ────────────────────────────────────────────

    print_section("MENSAJES INTER-AGENTE (TRAZABILIDAD)")
    for i, msg in enumerate(result.get("messages", []), 1):
        from_a = msg.get("from_agent", "?")
        to_a   = msg.get("to_agent", "?")
        phase  = msg.get("phase", "?")
        status = msg.get("status", "?")
        print(f"  [{i:2d}] {from_a:<15} → {to_a:<15} | {phase:<12} | {status}")

    print_section("PLAN DE EJECUCIÓN (SUBTAREAS)")
    for task in result.get("plan", []):
        icon = {"pending": "○", "active": "◉", "done": "✓", "failed": "✗"}.get(task["status"], "?")
        print(f"  {icon} [{task['id']}] {task['description']} (→ {task['agent']})")

    # Auditoría de herramientas en SQLite
    bus = MessageBus(session.session_id)
    tool_history = bus.get_session_tools()
    if tool_history:
        print_section("HERRAMIENTAS EJECUTADAS (AUDITORÍA SQLITE)")
        for th in tool_history:
            status_ico = "✓" if th.get("success") else "✗"
            print(f"  {status_ico} Herramienta: {th.get('tool_name')} | Tarea: {th.get('task_id')}")

    print_section("COHERENCIA COGNITIVA (NCM)")
    score = result.get("coherence_score", 1.0)
    bar   = "█" * int(score * 20) + "░" * (20 - int(score * 20))
    print(f"  Score: {score:.3f} [{bar}]")

    print_section("MÉTRICAS")
    metrics = result.get("metrics", {})
    print(f"  ⏱  Tiempo:           {metrics.get('elapsed_seconds', '?')}s")
    print(f"  🔄 Iteraciones:      {metrics.get('iterations', '?')}")
    print(f"  📋 Replanificaciones: {metrics.get('replan_count', '?')}")
    print(f"  💬 Mensajes:         {metrics.get('message_count', len(result.get('messages', [])))}")

    print_section("ESTADO FINAL")
    print(f"  Estado: {result.get('status', '?')}")

    print_section("RESPUESTA FINAL")
    answer = result.get("final_answer", "Sin respuesta")
    print(f"\n{answer}\n")

    print(SEPARATOR)
    print(f"✅ Demo completado con éxito. Registro auditado en nexo_data.db.\n")

    return result


if __name__ == "__main__":
    result = run_demo()
    sys.exit(0 if result.get("status") == "COMPLETED" else 1)
