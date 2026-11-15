# Diagramas NEXO

## Secuencia de misión

```mermaid
sequenceDiagram
  actor U as Usuario
  participant UI as Dashboard
  participant API as FastAPI
  participant O as Orquestador
  participant A as Analyst
  participant S as Planner
  participant X as Developer
  participant T as Herramienta
  participant R as Researcher
  participant Q as QA
  participant SC as Security
  participant E as Evaluador
  participant H as Harness
  participant DB as SQLite / Chroma
  U->>UI: objetivo
  UI->>API: POST /sessions
  API->>O: ejecutar sesión
  O->>A: solicitud y contexto
  A-->>O: análisis estructurado
  O->>S: análisis + objetivo
  S-->>O: plan validado o fallback acotado
  O->>X: tareas ordenadas
  X->>T: acción real
  T-->>X: salida observada
  X-->>O: evidencia
  opt misión compuesta
    O->>R: evidencia observada y objetivo
    R-->>O: síntesis con IDs de tareas
  end
  O->>Q: plan y resultados
  Q-->>O: checks de calidad
  O->>SC: auditoría de Skills/permisos
  SC-->>O: autorización o bloqueo
  O->>E: objetivo + criterios + evidencia
  alt aprobado
    E-->>O: APPROVED
    O->>DB: persistir sesión y memoria aprobada
  else requiere corrección
    E-->>O: REJECTED / NEEDS_CORRECTION
    O->>S: reintento limitado
  end
  H-->>O: límites, telemetría y auditoría
```

## Datos

```mermaid
flowchart TD
  SM[StateManager] --> O[Orquestador]
  O <--> MB[MessageBus]
  MB --> SQL[(SQLite: sesiones y eventos)]
  O --> MEM[Memoria]
  MEM --> CH[(Chroma: recuerdos aprobados)]
  MEM --> EMB[Ollama embeddings]
  UI[Dashboard web / Streamlit] <--> API[FastAPI]
```
