# Tecnologías de NEXO

## Python

Python es el lenguaje que implementa el backend, los agentes y las herramientas. Las funciones contienen operaciones; las clases agrupan datos y comportamiento. Las anotaciones de tipo documentan el contrato sin reemplazar la validación.

```python
# nexo/core/orquestador.py
def ejecutar_mision_completa(objetivo_usuario: str, config_dict: dict) -> dict:
    providers = {role: dict(cfg) for role, cfg in PROVIDER_CONFIG.items()}
    providers.update({role: dict(cfg) for role, cfg in config_dict.items()})
    manager = StateManager()
    session = manager.create_session(objetivo_usuario)
    return Orchestrator(manager, provider_config=providers).run(session.session_id)
```

## LLM, agentes y orquestador

Un LLM (modelo grande de lenguaje) produce texto a partir de instrucciones y contexto. La respuesta es probabilística y se valida con contratos y evidencia. Un agente es un componente con una responsabilidad, instrucciones, proveedor y, a veces, herramientas. El orquestador es código Python que controla el orden, el estado compartido y los límites de reintentos; no es una decisión autónoma ilimitada.

```python
# nexo/core/orchestrator.py: secuencia central del pipeline
agents = self._build_agents(bus)
analysis = self._phase_analysis(session, bus, agents)
plan = self._phase_planning(session, bus, agents, analysis)
execution_results = self._phase_execution(session, bus, agents, plan)
evaluation = self._phase_evaluation(session, bus, agents, analysis, plan, execution_results)
```

## Ollama y modelos locales

Ollama sirve modelos mediante una API local. El modelo predeterminado de los cuatro agentes es `qwen2.5-coder:7b`; una llamada estructurada local confirmó que responde con JSON para los contratos. Cada rol se puede sobrescribir con `NEXO_MODEL_ANALYST`, `NEXO_MODEL_STRATEGIST`, `NEXO_MODEL_EXECUTOR` o `NEXO_MODEL_EVALUATOR`. `nomic-embed-text` genera vectores para Chroma. Aunque `gemma4:12b-mlx` está instalado, en esta misión no respetó la salida estructurada ni con modo JSON, por lo que dejó de ser el valor predeterminado.

```bash
ollama list
ollama run qwen2.5-coder:7b "Responde solamente NEXO_OLLAMA_OK"
```

El primer comando inspecciona modelos instalados; el segundo realiza inferencia real. Si el proveedor Ollama configurado falla, NEXO informa el error y no reemplaza el modelo por un mock de forma silenciosa.

## LangChain

LangChain ofrece interfaces comunes para modelos y herramientas. En NEXO se usa en la ruta de herramientas directas de Streamlit: las funciones reciben argumentos estructurados y pueden enlazarse al agente Ejecutor. El flujo principal coordinado por FastAPI usa proveedores y contratos propios del proyecto.

## Herramientas

Una herramienta convierte argumentos en una observación o acción. `ToolRegistry` registra herramientas de diagnóstico, `SecurityPolicy` verifica operaciones y `safe_execute` captura fallos. La ruta LangChain tiene funciones de lectura/escritura de archivos y ejecución Python; requiere cuidado porque ejecutar Python permite las capacidades del proceso que la invoca.

## Persistencia: SQLite y Chroma

SQLite conserva sesiones, mensajes, ejecuciones de herramientas y eventos de coherencia. Chroma almacena resultados aprobados para recuperación semántica. Ollama embeddings convierte consulta y documentos en vectores; Chroma recupera los vecinos más cercanos. La colección vacía se detecta antes de solicitar embeddings.

```python
# nexo/core/memory.py
def buscar_en_memoria(consulta: str, cantidad: int = 2) -> str:
    vectorstore = Chroma(persist_directory=DB_PATH, embedding_function=obtener_embeddings())
    if vectorstore._collection.count() == 0:
        return ""
    docs = vectorstore.similarity_search(consulta, k=cantidad)
    return "\n".join(doc.page_content for doc in docs)
```

El orquestador consulta memoria antes de analizar y guarda el resultado únicamente cuando el Evaluador aprobó la misión y el flujo no usa mocks.

## FastAPI, Uvicorn y Streamlit

FastAPI implementa la API HTTP y valida solicitudes; Uvicorn sirve la aplicación ASGI. El Dashboard HTML/CSS/JavaScript consume estos endpoints. Streamlit es un framework Python para interfaces interactivas escritas como scripts; NEXO lo conserva como UI complementaria para iniciar el pipeline y probar las herramientas LangChain.

## HTML, CSS y JavaScript

HTML estructura los paneles, CSS adapta colores y distribución a pantallas y JavaScript envía solicitudes REST, consulta el progreso y representa agentes, plan, mensajes, herramientas, memoria, métricas e historial provenientes de la API.

## Docker

Docker empaqueta la API en un contenedor y Compose coordina API y Ollama. Los modelos no se descargan automáticamente; deben estar presentes en Ollama. La configuración Compose se validó, pero eso por sí solo no demuestra una construcción de imagen.
