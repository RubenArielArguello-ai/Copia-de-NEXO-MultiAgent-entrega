# Agentes, skills y herramientas

Los agentes son implementaciones LLM con instrucciones de rol y contratos de entrada/salida. Sus skills describen su responsabilidad. Las herramientas son funciones concretas registradas para producir observaciones o acciones; una skill no es una herramienta.

| Rol funcional | Implementación | Responsabilidad y control |
|---|---|---|
| Orchestrator | `nexo/core/orchestrator.py` | Coordinador único en Python: controla mensajes, dependencias, Harness, fases, reintentos, evaluación y entrega. No es un agente LLM independiente. |
| Researcher / Analyst | `nexo/agents/researcher.py`, `analyst.py` | Analyst interpreta la misión y define criterios. Researcher se activa en misiones compuestas, sintetiza resultados observados y cita IDs de tareas; no produce evidencia nueva. |
| Planner / Strategist | `nexo/agents/strategist.py` | Propone tareas y dependencias; el Orchestrator valida y normaliza cada tarea contra Skill Registry. |
| Developer / Executor | `nexo/agents/executor.py` | Selecciona Skill, valida permisos en Skill Registry/Security Core, llama herramientas registradas y devuelve evidencia observada. |
| QA | `nexo/agents/quality.py` | Revisión determinista independiente de tareas completadas, outputs no vacíos y cobertura del informe. Corre antes de Evaluator. |
| Security | `nexo/agents/security.py` | Gate fail-closed: coteja herramienta, Skill, agente y permiso con la auditoría de ejecución. |
| Evaluator | `nexo/agents/evaluator.py` | Verifica evidencia directa y gates QA/Security; aprueba solo cuando las herramientas requeridas están cubiertas. Rechaza evidencia literal contradictoria. |

## Skills, herramientas y monitor

`nexo/tools/base_tool.py` contiene el registro, las políticas y el contrato común. Entre las herramientas registradas están los diagnósticos de sistema, red y puertos, además de operaciones de archivo expuestas por las herramientas básicas según la configuración y reglas de selección. No se debe describir esto como shell irrestricto. `CoherenceMonitor` (`nexo/tools/coherence_monitor.py`) sí está implementado: el Orquestador le consulta consistencia del objetivo, duplicaciones, contradicciones, dependencias y riesgo de ciclo. No es un agente ni un LLM adicional.

`nexo/skills/registry.py` mantiene metadatos versionados de las capacidades, las selecciona por misión/tarea y autoriza su uso por agente/permisos antes de que el Ejecutor llame al ToolRegistry. El Orquestador agrega al plan todas las Skills que detecta en la misión y conserva el informe al final para que reciba resultados previos. Las Skills ejecutables incluyen diagnósticos de sistema/red, disponibilidad TCP/HTTP pública, análisis de logs, análisis estático de Python, informe basado en evidencias y lectura/escritura limitada al workspace.

`nexo/agents/base_agent.py` comparte inferencia, parsing, publicación de mensajes, telemetría y reserva de llamadas al Harness. Los mensajes estructurados están definidos en `nexo/schemas/message.py` y se transportan/persisten con `nexo/core/message_bus.py`. QA y Security son revisores deterministas, no se presentan como modelos LLM.

## Proveedores

Los roles Analista, Estratega, Ejecutor y Evaluador reciben proveedores según `nexo/config.py`. Cada uno tiene variable `NEXO_MODEL_<ROL>`; el valor predeterminado actual es `qwen2.5-coder:7b`. `MockProvider` se selecciona explícitamente para pruebas, no es fallback silencioso del modo Ollama. El Orquestador tiene una clave de configuración disponible, pero su coordinación principal no hace inferencia LLM.
