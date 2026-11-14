# Agentes, modelos y herramientas

| Agente | Archivo/clase | Responsabilidad | Modelo predeterminado | Herramientas |
|---|---|---|---|---|
| Analista | `nexo/agents/analyst.py`, `AnalystAgent` | Interpreta el pedido, detecta datos faltantes e identifica criterios verificables. | `qwen2.5-coder:7b` | Ninguna; razona sobre el texto recibido. |
| Estratega | `nexo/agents/strategist.py`, `StrategistAgent` | Divide el objetivo en tareas, asignaciones y dependencias. | `qwen2.5-coder:7b` | Ninguna; genera el plan. |
| Ejecutor | `nexo/agents/executor.py`, `ExecutorAgent` | Ejecuta una subtarea, interpreta datos reales y reporta evidencia en JSON. | `qwen2.5-coder:7b` | `NetworkDiagnosticTool`, `SystemDiagnosticTool`, `PortCheckTool`, seleccionadas por `_try_tool()`. |
| Evaluador | `nexo/agents/evaluator.py`, `EvaluatorAgent` | Compara plan, resultados y evidencia con el objetivo y criterios; devuelve veredicto estructurado. | `qwen2.5-coder:7b` | No ejecuta herramientas; evalúa los resultados proporcionados. |
| Orquestador | `nexo/core/orchestrator.py`, `Orchestrator` | Mantiene el ciclo, estado, dependencias, replanificación, límites y entrega. | No hace llamada LLM propia. | NCM y proveedores construidos para los agentes. |

## Contrato de agente

`BaseAgent` define `system_prompt`, `process(msg)` y `run()`. `run()` consume un mensaje dirigido al agente, llama `process`, publica la respuesta y la devuelve. `msg.reply()` mantiene la relación con el objetivo y emisor original. El payload transporta datos estructurados y `evidence` conserva razones breves legibles.

El Evaluador acepta `APPROVED`, `NEEDS_CORRECTION` o `REJECTED`. Una respuesta inválida se degrada a `REJECTED`. El campo `approved` del resultado final solo es verdadero cuando la evaluación registrada es `APPROVED`; que la sesión haya terminado no significa que se haya aprobado el objetivo.

## NCM

`CoherenceMonitor` es una herramienta de observación, no un agente conversacional. Revisa objetivo, plan, historial y número de iteración. Puede señalar desviación, duplicación, contradicción, dependencias ausentes o riesgo de ciclo. El Orquestador registra sus hallazgos y decide si replanificar.

## Selección del proveedor

La factoría `build_provider(role, config)` usa `OllamaProvider` si el servidor y el modelo están disponibles; si la configuración real no está disponible, falla explícitamente. `MockProvider` solo se selecciona mediante `type: mock`. Los defaults centrales son Gemma4 para análisis, estrategia y evaluación, y Qwen2.5-Coder para ejecución. Se pueden sobrescribir mediante `NEXO_MODEL_ANALYST`, `NEXO_MODEL_STRATEGIST`, `NEXO_MODEL_EXECUTOR`, `NEXO_MODEL_EVALUATOR`, `NEXO_MODEL_ORCHESTRATOR`.

La UI Streamlit directa usa `ChatOllama` y herramientas LangChain de archivo/Python. Es un camino independiente del Ejecutor del pipeline. Su modelo se selecciona en pantalla.
