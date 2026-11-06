# NEXO — Arquitectura Técnica

Este documento describe la arquitectura global del sistema NEXO, sus componentes fundamentales, patrones de diseño, modelo de datos y protocolos de comunicación inter-agente.

---

## 1. Visión General de la Arquitectura

NEXO está diseñado bajo una **arquitectura multiagente jerárquica con orquestador central y bus de mensajes in-process respaldado por SQLite**. No utiliza frameworks de orquestación de caja negra (como LangChain o AutoGen), garantizando control total del flujo cognitivo, determinismo y auditabilidad.

```
┌─────────────────────────────────────────────────────────────┐
│                      CAPA DE INTERFAZ                       │
│      Dashboard Web (HTML5/CSS3/JS)  │  API REST (FastAPI)    │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / JSON
┌──────────────────────────────▼──────────────────────────────┐
│                    ORQUESTADOR CENTRAL                      │
│   - Control de objetivo global   - Máquina de estados       │
│   - Planificación de fases       - Circuit breaker / replan │
└──────┬───────────────────────┬───────────────────────┬──────┘
       │                       │                       │
┌──────▼──────┐         ┌──────▼──────┐         ┌──────▼──────┐
│   ANALISTA  │         │  ESTRATEGA  │         │  EVALUADOR  │
│ Gemma4:12b  │         │ Gemma4:12b  │         │ Gemma4:12b  │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                       │
       └───────────────────────┼───────────────────────┘
                               │
                        ┌──────▼──────┐
                        │  EJECUTOR   │
                        │ Qwen2.5:7b  │
                        └──────┬──────┘
                               │ Ejecución
             ┌─────────────────┴─────────────────┐
             ▼                                   ▼
┌─────────────────────────┐         ┌─────────────────────────┐
│ NetworkDiagnosticTool   │         │ NEXO-Coherence Monitor  │
│ (L1-L4 OS commands)     │         │ (Jaccard Semántico/NCM) │
└─────────────────────────┘         └─────────────────────────┘
                               ▲
                               │ Eventos & Grafo
┌──────────────────────────────┴──────────────────────────────┐
│                   INFRAESTRUCTURA Y ESTADO                  │
│   MessageBus (Queue in-process) │ StateManager (Sessions)   │
│   Persistencia SQLite (nexo_data.db) │ BaseLLMProvider     │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Componentes del Núcleo (`nexo/core/`)

### 2.1. `Orchestrator` (`nexo/core/orchestrator.py`)
Es el director cognitivo. Controla el ciclo de vida de la resolución en 10 etapas (Percepción a Entrega).
- **Invariante de objetivo:** Asegura que todos los agentes trabajen sobre el objetivo formalizado.
- **Resolución de dependencias:** Impide la ejecución de subtareas cuyos prerrequisitos no hayan concluido con éxito.
- **Circuit Breaker:** Limita las iteraciones (`max_iterations = 5`) y ciclos de replanificación (`max_replanning_cycles = 2`) para impedir bucles infinitos.
- **Fusión de resultados:** Consolida el veredicto del Evaluador o extrae el mejor hallazgo en caso de terminación forzada.

### 2.2. `MessageBus` (`nexo/core/message_bus.py`)
Mecanismo desacoplado de transporte inter-agente.
- Mantiene una cola FIFO in-process (`collections.deque`) para comunicación asíncrona/síncrona sin latencia de red.
- Persistencia automática de cada `NexoMessage` a SQLite en tiempo real.
- Permite consultar el historial completo o auditar el grafo de mensajes.

### 2.3. `StateManager` (`nexo/core/state_manager.py`)
Gestiona el estado en memoria de las sesiones activas (`SessionState` y `SubTask`).
- Métricas de ejecución: timestamps de inicio/fin, duración por fase, conteo de mensajes e iteraciones.
- Estado de subtareas: `pending`, `active`, `done`, `failed`.
- Puntuación de coherencia acumulada (`coherence_score`).

---

## 3. Capa de Agentes Especializados (`nexo/agents/`)

Cada agente hereda de `BaseAgent` (`nexo/agents/base_agent.py`), encapsulando su identidad, proveedor de LLM y system prompt especializado:

| Agente | Clase | Especialidad (Skill) | Modelo Principal | Fallback |
|---|---|---|---|---|
| **Analista** | `AnalystAgent` | Comprensión, extracción de hipótesis y criterios de éxito | `gemma4:12b-mlx` | `MockProvider` |
| **Estratega** | `StrategistAgent` | Descomposición en grafo de subtareas atómicas y dependencias | `gemma4:12b-mlx` | `MockProvider` |
| **Ejecutor** | `ExecutorAgent` | Diagnóstico técnico mediante herramientas y análisis de telemetría | `qwen2.5-coder:7b` | `MockProvider` |
| **Evaluador** | `EvaluatorAgent` | QA crítico, verificación de evidencias contra criterios de éxito | `gemma4:12b-mlx` | `MockProvider` |

---

## 4. Herramientas del Sistema (`nexo/tools/`)

### 4.1. `NetworkDiagnosticTool` (Herramienta Real del Entorno)
Ejecuta diagnósticos secuenciales en capas de red (L1 a L4):
1. **L1 (Interfaz):** Inspección de interfaces activas (`ifconfig`, `ipconfig`, `ip addr`).
2. **L2 (Gateway):** Detección de ruta predeterminada (`netstat -rn`, `ip route`) y verificación ICMP ping.
3. **L3 (DNS):** Resolución de nombres (`google.com`, `cloudflare.com`, etc.) mediante sockets del sistema operativo.
4. **L4 (Internet):** Conectividad hacia direcciones Anycast públicas (`8.8.8.8`, `1.1.1.1`).
5. **Diagnóstico Consolidado:** Identifica causa raíz (`NO_INTERFACE`, `NO_GATEWAY`, `DNS_FAILURE`, `INTERNET_UNREACHABLE`, `FULLY_CONNECTED`) y provee recomendaciones de mitigación.

### 4.2. `NEXO-Coherence Monitor` (Herramienta de Innovación Propia)
Inspecciona el grafo de mensajes inter-agente y la estructura del plan para identificar fallos cognitivos:
- **Desviación de Objetivo (`GOAL_DEVIATION`):** Similitud de Jaccard entre objetivo y contenido reciente (< 0.15).
- **Duplicación Semántica (`TASK_DUPLICATION`):** Similitud de Jaccard entre tareas del plan (≥ 0.60).
- **Contradicciones Lógicas (`CONTRADICTION`):** Pares antonímicos opuestos entre mensajes de distintos agentes.
- **Dependencias Inválidas (`MISSING_DEPENDENCY`):** Subtareas que dependen de identificadores no existentes en el plan.
- **Riesgo de Bucle (`CYCLE_RISK`):** Límite preventivo de iteraciones alcanzado.

---

## 5. Protocolo de Comunicación (`NexoMessage`)

El protocolo de intercambio está definido formalmente en `nexo/schemas/message.py`:

```python
@dataclass
class NexoMessage:
    from_agent:      AgentID              # Emisor
    to_agent:        AgentID              # Receptor
    task_id:         str                  # ID de sesión / tarea
    goal:            str                  # Objetivo global inmutable
    phase:           TaskPhase            # Fase del ciclo cognitivo
    payload:         dict[str, Any]       # Contenido estructurado (JSON)
    msg_id:          str                  # UUID v4 único
    context:         dict[str, Any]       # Contexto histórico
    evidence:        list[str]            # Evidencias recolectadas
    status:          MessageStatus        # PENDING | ACTIVE | COMPLETED | PARTIAL | FAILED | BLOCKED
    next_action:     Optional[str]        # Sugerencia de siguiente acción
    coherence_flags: list[CoherenceFlag]  # Anomalías NCM anotadas
    timestamp:       str                  # ISO 8601 UTC
    iteration:       int                  # Número de ciclo cognitivo
```

---

## 6. Persistencia y Almacenamiento

El motor de persistencia utiliza **SQLite 3** (`nexo_data.db`):

- **Tabla `sessions`:**
  - `session_id` (TEXT, PK): Identificador UUID de la sesión.
  - `request` (TEXT): Solicitud original del usuario.
  - `status` (TEXT): `CREATED`, `RUNNING`, `COMPLETED`, `FAILED`, `REPLANNING`.
  - `created_at`, `updated_at` (TEXT): Timestamps ISO.
  - `summary` (TEXT): Resumen JSON con métricas, plan y respuesta final.

- **Tabla `messages`:**
  - `id` (INTEGER, PK AUTOINCREMENT)
  - `msg_id` (TEXT, UNIQUE): UUID del mensaje.
  - `session_id` (TEXT, INDEX): Referencia a la sesión.
  - `from_agent`, `to_agent`, `phase`, `status`, `goal`: Metadatos del protocolo.
  - `payload`, `evidence`, `flags`: Cargas serializadas en JSON.
  - `iteration`, `timestamp`: Trazabilidad temporal.

---

## 7. Capa de Servicios y Frontend

- **API REST (`api/main.py`):** Construida con FastAPI, proporciona endpoints no bloqueantes para creación y polling de sesiones:
  - `POST /sessions`: Crea una sesión e inicia la ejecución en background.
  - `GET /sessions/{id}`: Consulta de telemetría, métricas y estado del plan.
  - `GET /sessions/{id}/messages`: Historial granular de mensajes.
  - `GET /health`: Estado del servicio.
- **Frontend SPA (`frontend/`):** Dashboard moderno vanilla (HTML5, CSS3, ES6) sin herramientas de compilación externas. Visualiza en vivo el ciclo cognitivo, la actividad de los 5 agentes, el grafo de tareas y el indicador radial del CoherenceScore.

---

## 8. Trazabilidad con ADRs (Decisiones de Arquitectura)

| Componente | Decisión | ADR Asociado |
|---|---|---|
| Lenguaje | Python 3.10+ | ADR-001 |
| Abstracción LLM | `BaseLLMProvider` (Ollama + Mock) | ADR-002 |
| Modelos de Agentes | `gemma4:12b-mlx` y `qwen2.5-coder:7b` | ADR-003 |
| Bus de Mensajes | In-process deque + SQLite | ADR-004 |
| Protocolo | `NexoMessage` con dataclass y enums | ADR-005 |
| Monitor NCM | Similitud de Jaccard y grafo de dependencias | ADR-006 / ADR-007 |
| API & Frontend | FastAPI + Vanilla SPA | ADR-008 |
| Persistencia | SQLite estándar sin ORM pesado | ADR-009 |
| Circuit Breaker | 5 iteraciones / 2 replanificaciones | ADR-010 |
| Diagnóstico | Ejecución real en sistema operativo | ADR-011 |
