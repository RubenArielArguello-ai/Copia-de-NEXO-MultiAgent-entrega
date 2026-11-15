# NEXO — sistema cognitivo multiagente

NEXO es una plataforma multiagente para diagnóstico y automatización técnica controlada. FastAPI recibe misiones, un Orchestrator central coordina especialistas, Skill Registry y Security revisan las ejecuciones y QA/Evaluator contrastan los resultados con evidencia real. Ollama es el proveedor local principal.

## Arquitectura y responsabilidades

| Componente | Implementación | Responsabilidad |
|---|---|---|
| Orquestador | `nexo/core/orchestrator.py` | Coordina fases, mensajes, estado, replanificación limitada, coherencia y entrega. Es código Python, no un agente LLM en el flujo principal. |
| Analyst | `nexo/agents/analyst.py` | Interpreta misión y criterios medibles. |
| Planner | `nexo/agents/strategist.py` | Descompone tareas y propone dependencias, validadas por Orchestrator. |
| Developer | `nexo/agents/executor.py` | Ejecuta Skills y herramientas autorizadas y devuelve evidencia observada. |
| Researcher | `nexo/agents/researcher.py` | En misiones compuestas sintetiza resultados de ejecución sin crear evidencia. |
| QA | `nexo/agents/quality.py` | Comprueba completitud y evidencia del informe mediante reglas deterministas. |
| Security | `nexo/agents/security.py` | Revisa autorización de Skills y bloquea si faltan pruebas de permisos. |
| Evaluator | `nexo/agents/evaluator.py` | Verifica el objetivo, los gates y evidencia antes de aprobar. |

Los agentes, Skills y Tools son capas separadas. `nexo/skills/registry.py` registra capacidades versionadas, permite descubrirlas y seleccionar las pertinentes para una misión mixta; el Orchestrator incorpora esas capacidades al plan y el Executor autoriza cada una antes de utilizar el ToolRegistry. Incluye diagnósticos de sistema/red, comprobación TCP/HTTP pública, análisis de logs, análisis estático de Python, informes basados en evidencia y operaciones de archivo limitadas al workspace.

FastAPI (`api/main.py`) publica la API y sirve el Dashboard (`frontend/`). `app.py` ofrece una interfaz Streamlit cliente de la API. `MessageBus` persiste sesiones y mensajes en SQLite; `nexo/core/memory.py` usa Chroma para recuerdos aprobados. La memoria recuperada da contexto y no sustituye evidencia de la misión en curso.

## Ollama y modelos locales

`nexo/config.py` define proveedor, modelos y límites. El default es `qwen2.5-coder:7b`, configurable con `NEXO_MODEL_ANALYST`, `NEXO_MODEL_STRATEGIST`, `NEXO_MODEL_EXECUTOR`, `NEXO_MODEL_EVALUATOR` y `NEXO_MODEL_RESEARCHER` (hereda Analyst por defecto). `OLLAMA_HOST` define el endpoint. El proveedor reutiliza conexiones, verifica disponibilidad y registra latencia/contadores de tokens. QA y Security son políticas locales, no modelos simulados. Si Ollama o el modelo no está disponible, la misión real falla explícitamente.

El Harness aplica timeout (`NEXO_SESSION_TIMEOUT`), presupuesto de tareas (`NEXO_MAX_TOOL_EXECUTIONS`), presupuesto de inferencias (`NEXO_MAX_LLM_CALLS`), parada de emergencia (`NEXO_EMERGENCY_STOP=true` o archivo `NEXO_EMERGENCY_STOP_FILE`) y auditoría por misión. La parada opera entre inferencias/herramientas; no mata llamadas nativas ya bloqueadas.

Chroma genera embeddings locales con `nomic-embed-text`; ese modelo es para memoria semántica. La disponibilidad debe verificarse en el host de despliegue.

## Evidencia de funcionamiento

El 2026-11-14 se ejecutó una misión end-to-end usando Ollama local `qwen2.5-coder:3b` y datos reales del host. Analyst, Planner, Developer, Researcher, QA, Security y Evaluator publicaron mensajes trazables; QA y Security aprobaron sus gates y Evaluator entregó `APPROVED`. System Diagnostics informó 10 CPUs lógicas, 16 GiB RAM y 96,3% de disco usado; Network Diagnostics observó `FULLY_CONNECTED`. El Harness registró 5 inferencias, 3 herramientas, 0 bloqueos y 116,99 s. La sesión usó SQLite/Chroma temporales; no se modificaron archivos del workspace para esta prueba.

## Inicio local

Requisitos: Python 3.10+, dependencias de `requirements.txt`, Ollama y los modelos configurados.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
ollama serve
```

En otra terminal, iniciar FastAPI con `uvicorn api.main:app --reload --host 127.0.0.1 --port 8000` y abrir `http://127.0.0.1:8000`. El API limita el tamaño de misión y aplica rate limiting. `NEXO_API_TOKEN` habilita bearer auth; en producción es obligatorio. Variables: [`.env.example`](.env.example). Contratos API: [`docs/API.md`](docs/API.md). Para Compose, exportar `NEXO_API_TOKEN` y descargar en el servicio Ollama los modelos que estén configurados (por defecto `qwen2.5-coder:7b`; `nomic-embed-text` si se usa memoria). No se publica el puerto de Ollama. Streamlit puede iniciarse con `streamlit run app.py`.

## Material de entrega

- [Arquitectura](ARQUITECTURA.md), [agentes y herramientas](AGENTES.md), [flujo](FLUJO_DE_EJECUCION.md) y [tecnologías](TECNOLOGIAS.md).
- [Guía de presentación y defensa](GUIA_PRESENTACION.md), [informe final](INFORME_FINAL.md) y [diagrama](DIAGRAMA.md).
- [Presentación editable](NEXO_FINAL.pptx) y su copia de compatibilidad `PRESENTACION_NEXO_FINAL.pptx`.

## Alcance y limitaciones

La ejecución de tareas es secuencial; no hay aislamiento concurrente del bus y del estado. Researcher no navega fuentes externas. Code Engineering analiza estáticamente y no modifica ni ejecuta proyectos. HTTP Health Check permite solo IPs públicas y no sigue redirecciones. Los informes consolidan evidencia observada. Los timeouts de herramientas no pueden finalizar hilos Python nativos ya bloqueados. La retención de Chroma depende del operador y aún no tiene TTL ni API de borrado por usuario. Más límites y verificaciones pendientes: [`PENDIENTES.md`](PENDIENTES.md).
