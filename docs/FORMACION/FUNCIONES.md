# Funciones importantes

## Entrada y coordinación

| Función | Archivo | Recibe | Devuelve / efecto |
|---|---|---|---|
| `create_session(body)` | `api/main.py` | JSON con `request` no vacío | Crea estado, agenda el pipeline y responde con `session_id`. |
| `_run_session(session_id)` | `api/main.py` | ID de sesión | Ejecuta `Orchestrator.run()` y actualiza estado de worker. |
| `Orchestrator.run(session_id)` | `nexo/core/orchestrator.py` | ID existente en `StateManager` | Ejecuta fases, persiste mensajes y devuelve estado, respuesta, aprobación, plan y métricas. |
| `_build_agents(bus)` | `nexo/core/orchestrator.py` | Bus de la sesión | Construye Analista, Estratega, Ejecutor y Evaluador con sus proveedores. |
| `_phase_analysis(...)` | `nexo/core/orchestrator.py` | Sesión, bus y agentes | Envía solicitud al Analista; devuelve el diccionario de análisis. |
| `_phase_planning(...)` | `nexo/core/orchestrator.py` | Sesión, bus, agentes y análisis | Pide al Estratega tareas con dependencias y registra subtareas. |
| `_phase_execution(...)` | `nexo/core/orchestrator.py` | Sesión, bus, agentes y plan | Respeta dependencias, ejecuta subtareas y devuelve resultados. |
| `_phase_evaluation(...)` | `nexo/core/orchestrator.py` | Análisis, plan y resultados | Obtiene el veredicto y guarda la evaluación en el estado. |
| `_run_coherence_check(...)` | `nexo/core/orchestrator.py` | Estado de sesión y bus | Ejecuta NCM, persiste el evento y devuelve score/anomalías/recomendación. |
| `_extract_best_answer(results)` | `nexo/core/orchestrator.py` | Resultados de ejecución | Extrae recomendación o conclusión más reciente como respuesta de respaldo. |

## Agentes y mensajes

| Función | Archivo | Qué hace |
|---|---|---|
| `BaseAgent.call_llm(prompt, **kwargs)` | `nexo/agents/base_agent.py` | Envía el prompt de sistema y de usuario al proveedor del rol. |
| `BaseAgent.parse_json_response(raw)` | `nexo/agents/base_agent.py` | Limpia bloques de pensamiento/Markdown, intenta parsear JSON y devuelve error estructurado si falla. |
| `BaseAgent.run()` | `nexo/agents/base_agent.py` | Consume, procesa y publica un mensaje. |
| `AnalystAgent.process(msg)` | `nexo/agents/analyst.py` | Produce interpretación, restricciones, faltantes y criterios de éxito. |
| `StrategistAgent.process(msg)` | `nexo/agents/strategist.py` | Devuelve plan y metadatos de estrategia. |
| `ExecutorAgent.process(msg)` | `nexo/agents/executor.py` | Ejecuta `_try_tool`, pide interpretación al modelo y devuelve `execution_result`. |
| `ExecutorAgent._try_tool(task, context)` | `nexo/agents/executor.py` | Selecciona sistema, puerto, red o ninguna herramienta según la subtarea. |
| `EvaluatorAgent.process(msg)` | `nexo/agents/evaluator.py` | Valida el veredicto permitido y devuelve evaluación con correcciones. |
| `NexoMessage.reply(...)` | `nexo/schemas/message.py` | Crea respuesta relacionada con el mensaje recibido. |

## Proveedores y herramientas

| Función | Archivo | Qué hace |
|---|---|---|
| `build_provider(role, config)` | `nexo/providers/base_provider.py` | Selecciona Ollama comprobado; si se configura `mock`, solo entonces crea `MockProvider`. |
| `OllamaProvider.generate(...)` | mismo archivo | Envía chat a Ollama con timeout, reintentos y telemetría. |
| `MockProvider.generate(...)` | mismo archivo | Devuelve fixtures por rol para pruebas sin inferencia real. |
| `ToolRegistry.execute_tool(name, context)` | `nexo/tools/base_tool.py` | Valida autorización/parámetros y ejecuta herramienta con manejo de errores. |
| `BaseTool.safe_execute(context)` | mismo archivo | Mide duración, valida parámetros y captura fallos. |
| `SecurityPolicy.validate_command(tokens)` | mismo archivo | Rechaza binarios y argumentos fuera de la política permitida. |
| `NetworkDiagnosticTool.execute(context)` | `nexo/tools/diagnostic_tool.py` | Consulta conectividad por capas y determina resultado de diagnóstico. |
| `SystemDiagnosticTool.execute(context)` | `nexo/tools/system_tool.py` | Reúne información básica de sistema y recursos. |
| `PortCheckTool.execute(context)` | `nexo/tools/port_tool.py` | Prueba conexión TCP a host/puerto. |
| `CoherenceMonitor.execute(context)` | `nexo/tools/coherence_monitor.py` | Devuelve score, anomalías y recomendación. |

## Persistencia, configuración y UI

| Función | Archivo | Qué hace |
|---|---|---|
| `MessageBus.publish/consume()` | `nexo/core/message_bus.py` | Encola mensajes y entrega el próximo dirigido al agente. |
| `MessageBus.record_tool_execution()` | mismo archivo | Persiste parámetros, salida y éxito de herramienta. |
| `MessageBus.record_coherence_event()` | mismo archivo | Persiste score, anomalías y recomendación NCM. |
| `StateManager.create_session/get_session()` | `nexo/core/state_manager.py` | Crea y recupera estado en memoria. |
| `get_llm_for_role(role, config)` | `nexo/core/llm_factory.py` | Construye el modelo LangChain Ollama/OpenAI para la ruta directa. |
| `ejecutar_mision_completa(goal, config)` | `nexo/core/orquestador.py` | Construye una sesión y ejecuta el pipeline completo. |
| `ejecutar_mision(goal, config)` | mismo archivo | Adaptador simple que devuelve solo `final_answer`. |
| `ejecutar_mision_directa(goal, config)` | mismo archivo | Invoca el agente LangChain directo y sus herramientas. |
| `guardar_en_memoria(text)` / `buscar_en_memoria(query, k)` | `nexo/core/memory.py` | Inserta y consulta documentos en Chroma con embeddings Ollama. |
| `startSession()` / `poll()` | `frontend/app.js` | Inicia una sesión REST y actualiza el dashboard mediante polling. |

### Ejemplo de llamada Python

```python
from nexo.core.orquestador import ejecutar_mision_completa
from nexo.config import PROVIDER_CONFIG

resultado = ejecutar_mision_completa(
    "Diagnosticar si la computadora tiene conectividad a Internet",
    PROVIDER_CONFIG,
)
print(resultado["status"], resultado["approved"], resultado["final_answer"])
```
