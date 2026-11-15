# Arquitectura

## Capas

1. `frontend/` ofrece el Dashboard web; `app.py` ofrece una vista Streamlit cliente.
2. `api/main.py` sirve la UI, crea sesiones y expone estado, mensajes, modelos, herramientas e historial.
3. `nexo/core/orchestrator.py` dirige fases y reintentos; `StateManager` mantiene estado en ejecución.
4. `nexo/agents/` implementa Analyst, Strategist/Planner, Executor/Developer, Researcher, QA, Security y Evaluator. El Orchestrator dirige el flujo; QA y Security aplican gates deterministas.
5. `nexo/providers/base_provider.py` enlaza Ollama real o `MockProvider` explícito.
6. `MessageBus` guarda mensajes/eventos en SQLite; `nexo/core/memory.py` usa Chroma para recuerdos aprobados.

```mermaid
flowchart LR
  UI[Frontend / Streamlit] --> API[FastAPI]
  API --> O[Orquestador Python]
  O --> A[Analyst]
  A --> S[Planner / Strategist]
  S --> X[Developer / Executor]
  X --> T[Herramientas autorizadas] --> X
  X --> R[Researcher opcional]
  R --> Q[QA gate]
  Q --> SEC[Security gate]
  SEC --> E[Evaluator]
  E -->|corrección limitada| S
  E -->|entrega| O
  O <--> MB[MessageBus]
  MB --> DB[(SQLite)]
  O --> M[Memoria Chroma]
  A -. Ollama .-> L[Proveedor local]
  S -. Ollama .-> L
  X -. Ollama .-> L
  R -. Ollama cuando se activa .-> L
  E -. Ollama .-> L
  Q -. policy local .-> O
  SEC -. policy local .-> O
```

## Configuración

Los modelos y el endpoint se centralizan en `nexo/config.py`. El Orquestador no genera texto con un LLM propio. Ollama fuera de servicio produce un error explícito; `MockProvider` solo se usa si se configura como `mock`. `MissionHarness` limita duración, cantidad de herramientas e inferencias por misión, y registra telemetría agregada.

## Persistencia

SQLite conserva sesiones y registros operativos. Chroma almacena experiencias aprobadas para búsqueda semántica; memoria recuperada sirve como contexto, no como evidencia de la misión actual.
