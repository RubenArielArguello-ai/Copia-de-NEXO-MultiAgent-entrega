# NEXO — sistema cognitivo multiagente

NEXO es un prototipo académico para atender misiones técnicas mediante agentes con responsabilidades separadas. El sistema interpreta una solicitud, propone un plan, ejecuta herramientas registradas y evalúa la evidencia obtenida. Las inferencias de los cuatro agentes usan modelos locales servidos por Ollama; la coordinación del flujo está implementada en Python.

## Arquitectura y responsabilidades

| Componente | Implementación | Responsabilidad |
|---|---|---|
| Orquestador | `nexo/core/orchestrator.py` | Coordina fases, mensajes, estado, replanificación limitada, coherencia y entrega. Es código Python, no un agente LLM en el flujo principal. |
| Analista | `nexo/agents/analyst.py` | Interpreta la misión, explicita restricciones y criterios de éxito. |
| Estratega | `nexo/agents/strategist.py` | Produce un plan breve con tareas y dependencias; el sistema valida que las acciones correspondan a capacidades disponibles. |
| Ejecutor | `nexo/agents/executor.py` | Selecciona y llama herramientas registradas; devuelve resultados observados. |
| Evaluador | `nexo/agents/evaluator.py` | Contrasta objetivo y resultados; aprueba solo con ejecución exitosa y evidencia suficiente. |

Los agentes, Skills y Tools son capas separadas. `nexo/skills/registry.py` registra capacidades versionadas, permite descubrirlas y seleccionar las pertinentes para una misión mixta; el Orchestrator incorpora esas capacidades al plan y el Executor autoriza cada una antes de utilizar el ToolRegistry. Incluye diagnósticos de sistema/red, comprobación TCP/HTTP pública, análisis de logs, análisis estático de Python, informes basados en evidencia y operaciones de archivo limitadas al workspace.

FastAPI (`api/main.py`) publica la API y sirve el Dashboard (`frontend/`). `app.py` ofrece una interfaz Streamlit cliente de la API. `MessageBus` persiste sesiones y mensajes en SQLite; `nexo/core/memory.py` usa Chroma para recuerdos aprobados. La memoria recuperada da contexto y no sustituye evidencia de la misión en curso.

## Ollama y modelos locales

`nexo/config.py` define el proveedor y el endpoint. El valor predeterminado actual para Analista, Estratega, Ejecutor y Evaluador es `qwen2.5-coder:7b`, configurable por `NEXO_MODEL_ANALYST`, `NEXO_MODEL_STRATEGIST`, `NEXO_MODEL_EXECUTOR` y `NEXO_MODEL_EVALUATOR`. `OLLAMA_HOST` cambia el endpoint (por defecto `http://127.0.0.1:11434`). Ollama expone `/api/chat`; el proveedor maneja formato JSON cuando se solicita, timeout, reintentos y telemetría. `MockProvider` solo se usa si se selecciona explícitamente para pruebas. Si Ollama no está disponible, el modo real falla explícitamente.

Chroma genera embeddings locales con `nomic-embed-text`; ese modelo es para memoria semántica, no uno de los cuatro agentes. La presencia de modelos debe verificarse en el equipo donde se hará la presentación.

## Evidencia de funcionamiento

La misión `ee0d35a4` finalizó **COMPLETED** y **APPROVED**, según el registro de ejecución comunicado para esta entrega. El archivo [`prueba_nexo_final.txt`](prueba_nexo_final.txt) fue escrito, leído y verificado correctamente; su contenido registrado es `NEXO verificado por escritura y lectura`. Esta evidencia corresponde a una misión real aprobada, no a una ejecución con mocks. No se volvió a ejecutar durante la preparación documental.

## Inicio local

Requisitos: Python 3.10+, dependencias de `requirements.txt`, Ollama y los modelos configurados.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
ollama serve
```

En otra terminal, iniciar la API con `uvicorn api.main:app --reload --host 127.0.0.1 --port 8000` y abrir `http://127.0.0.1:8000`. La API escucha en localhost por defecto, limita el tamaño de misión y aplica rate limiting. Si se configura `NEXO_API_TOKEN`, los endpoints requieren `Authorization: Bearer <token>`. En producción (`NEXO_ENV=production`) el token es obligatorio. Para Compose, exportar `NEXO_API_TOKEN` antes de iniciar. El puerto de Ollama no se publica al host. Si Ollama ya funciona como servicio, no iniciar otra instancia. Streamlit puede iniciarse con `streamlit run app.py`.

## Material de entrega

- [Arquitectura](ARQUITECTURA.md), [agentes y herramientas](AGENTES.md), [flujo](FLUJO_DE_EJECUCION.md) y [tecnologías](TECNOLOGIAS.md).
- [Guía de presentación y defensa](GUIA_PRESENTACION.md), [informe final](INFORME_FINAL.md) y [diagrama](DIAGRAMA.md).
- [Presentación editable](NEXO_FINAL.pptx) y su copia de compatibilidad `PRESENTACION_NEXO_FINAL.pptx`.

## Alcance y limitaciones

La salida depende de la calidad y disponibilidad del modelo local. El chequeo HTTP solo permite destinos con IP pública, usa la IP resuelta para esa conexión y no sigue redirecciones. El análisis de código es estático: detecta sintaxis y patrones de riesgo, pero no modifica ni ejecuta programas. Los informes solo consolidan salidas observadas de herramientas. La ruta auxiliar de Python fue retirada; las funciones de archivo usan la contención del workspace. La evaluación LLM puede equivocarse pese a las comprobaciones de evidencia.
