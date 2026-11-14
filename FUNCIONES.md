# Funciones y módulos principales

| Función | Archivo | Propósito |
|---|---|---|
| `create_session` | `api/main.py` | Valida solicitud, crea sesión y encola ejecución. |
| `_run_session` | `api/main.py` | Ejecuta el Orquestador para la sesión. |
| `Orchestrator.run` | `nexo/core/orchestrator.py` | Coordina etapas, límites, persistencia y entrega. |
| `_phase_analysis` | mismo | Envía objetivo al Analista. |
| `_phase_planning` | mismo | Pide plan, normaliza herramientas y registra dependencias. |
| `_phase_execution` | mismo | Ejecuta tareas respetando dependencias y guarda resultados. |
| `_phase_evaluation` | mismo | Pide veredicto basado en evidencia. |
| `BaseAgent.call_llm_json` | `nexo/agents/base_agent.py` | Solicita JSON y reintenta reparación limitada. |
| `parse_json_response` | mismo | Limpia y parsea la salida estructurada. |
| `ExecutorAgent._try_tool` | `nexo/agents/executor.py` | Selecciona y llama la herramienta autorizada. |
| `build_provider` | `nexo/providers/base_provider.py` | Construye proveedor Ollama o mock explícito. |
| `MessageBus.record_tool_execution` | `nexo/core/message_bus.py` | Persiste auditoría de herramienta en SQLite. |
| `guardar_en_memoria` / `buscar_en_memoria` | `nexo/core/memory.py` | Escribe/consulta recuerdos vectoriales en Chroma. |
| `api(path, ...)` | `app.py` | Conecta Streamlit a los mismos endpoints FastAPI. |

## Lectura sugerida

Empieza en `api/main.py`, sigue hacia `Orchestrator.run`, luego abre cada `_phase_*`, los agentes, proveedor y herramientas. Para entender los datos, revisa `nexo/schemas/message.py` y `nexo/core/state_manager.py`.
