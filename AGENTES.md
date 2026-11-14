# Agentes, skills y herramientas

Los agentes son implementaciones LLM con instrucciones de rol y contratos de entrada/salida. Sus skills describen su responsabilidad. Las herramientas son funciones concretas registradas para producir observaciones o acciones; una skill no es una herramienta.

| Rol | Archivo | Responsabilidad implementada |
|---|---|---|
| Orquestador | `nexo/core/orchestrator.py` | Coordina fases, estado y mensajes; controla ciclos y replanificaciones; consulta `CoherenceMonitor`; conduce la entrega. En el flujo principal es lógica Python, no un agente LLM. |
| Analista | `nexo/agents/analyst.py` | Interpreta solicitud, restricciones, datos faltantes y criterios verificables. |
| Estratega | `nexo/agents/strategist.py` | Genera plan limitado con tareas/dependencias y recuperación ante salida no válida. |
| Ejecutor | `nexo/agents/executor.py` | Pide acciones técnicas a `ToolRegistry`, ejecuta herramientas permitidas y devuelve su resultado observado. |
| Evaluador | `nexo/agents/evaluator.py` | Compara objetivo, plan y resultados; exige ejecución exitosa y evidencia antes de aprobar. Puede solicitar corrección. |

## Skills, herramientas y monitor

`nexo/tools/base_tool.py` contiene el registro, las políticas y el contrato común. Entre las herramientas registradas están los diagnósticos de sistema, red y puertos, además de operaciones de archivo expuestas por las herramientas básicas según la configuración y reglas de selección. No se debe describir esto como shell irrestricto. `CoherenceMonitor` (`nexo/tools/coherence_monitor.py`) sí está implementado: el Orquestador le consulta consistencia del objetivo, duplicaciones, contradicciones, dependencias y riesgo de ciclo. No es un agente ni un LLM adicional.

`nexo/skills/registry.py` mantiene metadatos versionados de las capacidades, las selecciona por misión/tarea y autoriza su uso por agente/permisos antes de que el Ejecutor llame al ToolRegistry. El Orquestador agrega al plan todas las Skills que detecta en la misión y conserva el informe al final para que reciba resultados previos. Las Skills ejecutables incluyen diagnósticos de sistema/red, disponibilidad TCP/HTTP pública, análisis de logs, análisis estático de Python, informe basado en evidencias y lectura/escritura limitada al workspace.

`nexo/agents/base_agent.py` comparte el ciclo de inferencia, parsing, publicación y respuesta de mensajes. Los mensajes estructurados están definidos en `nexo/schemas/message.py` y se transportan/persisten con `nexo/core/message_bus.py`.

## Proveedores

Los roles Analista, Estratega, Ejecutor y Evaluador reciben proveedores según `nexo/config.py`. Cada uno tiene variable `NEXO_MODEL_<ROL>`; el valor predeterminado actual es `qwen2.5-coder:7b`. `MockProvider` se selecciona explícitamente para pruebas, no es fallback silencioso del modo Ollama. El Orquestador tiene una clave de configuración disponible, pero su coordinación principal no hace inferencia LLM.
