# NEXO — Proceso Cognitivo

El proceso cognitivo de NEXO emula el ciclo de razonamiento humano para resolución de problemas, implementado como pipeline computacional de 10 etapas.

---

## Las 10 Etapas

### 1. Percepción
**Componente:** API REST / Frontend  
**Qué hace:** Recibe la solicitud del usuario y la transforma en una sesión con un ID único.  
**Entrada:** Texto libre del usuario  
**Salida:** `SessionState` con `original_request`, `session_id` y timestamp  

---

### 2. Interpretación
**Componente:** Agente Analista  
**Qué hace:** Analiza el texto del usuario sin asumir información no declarada. Identifica la categoría del problema, restricciones, información faltante e hipótesis iniciales.  
**LLM:** gemma4:12b-mlx  
**Salida:** JSON estructurado con `interpretation`, `success_criteria`, `missing_info`, `initial_hypotheses`  

> *El Analista es el primer filtro cognitivo. Si no puede categorizar el problema, lo reporta en lugar de inventar una categoría.*

---

### 3. Definición del Objetivo
**Componente:** Orquestador  
**Qué hace:** Toma el análisis del Analista y formaliza el objetivo global de la sesión. Este objetivo permanece inmutable durante todo el ciclo.  
**Salida:** Campo `goal` del `SessionState`  

---

### 4. Planificación
**Componente:** Agente Estratega  
**Qué hace:** Diseña un plan de resolución como grafo de subtareas con dependencias explícitas. Asigna cada tarea al agente correcto.  
**LLM:** gemma4:12b-mlx  
**Salida:** Lista de `SubTask` con `id`, `description`, `assigned_to`, `depends_on`  

> *El Estratega puede recibir el plan de vuelta con correcciones del Evaluador y replanificar.*

---

### 5. Decisión
**Componente:** Orquestador  
**Qué hace:** Respeta el orden de dependencias y decide qué tarea ejecutar en cada momento. No ejecuta una tarea si sus dependencias no están cumplidas.  
**Salida:** Mensajes `NexoMessage` hacia el Ejecutor con el contexto de cada subtarea  

---

### 6. Acción
**Componente:** Agente Ejecutor  
**Qué hace:** Es el único agente que interactúa con herramientas reales. Ejecuta comandos de sistema (ping, DNS, ifconfig), interpreta los resultados y los devuelve estructurados.  
**LLM:** qwen2.5-coder:7b (especializado en razonamiento técnico)  
**Herramientas:** `NetworkDiagnosticTool`  

---

### 7. Observación
**Componente:** NCM + StateManager  
**Qué hace:** El NEXO-Coherence Monitor analiza el grafo de mensajes acumulado en tiempo real. Detecta desviaciones, duplicaciones, contradicciones y dependencias incumplidas. Calcula el CoherenceScore.  
**Salida:** `CoherenceReport` con `score`, `anomalies` y `should_replan`  

---

### 8. Evaluación
**Componente:** Agente Evaluador  
**Qué hace:** Compara los resultados de ejecución contra los criterios de éxito definidos en la etapa de Interpretación. Verifica que la evidencia sea suficiente. Puede rechazar resultados vagos o contradictorios.  
**LLM:** gemma4:12b-mlx  
**Salida:** Veredicto `APPROVED | NEEDS_CORRECTION | REJECTED` con razones  

> *El Evaluador es el guardián de la calidad. Es intencionalmente exigente.*

---

### 9. Corrección
**Componente:** Orquestador  
**Qué hace:** Si el Evaluador rechaza o pide correcciones, el Orquestador envía las correcciones al Estratega para replanificación. Este ciclo puede repetirse hasta `max_replanning_cycles` veces.  
**Circuit Breaker:** Si `iteration >= max_iterations`, el Orquestador fuerza la entrega del mejor resultado disponible.  

---

### 10. Entrega
**Componente:** Orquestador + API  
**Qué hace:** Cuando el Evaluador aprueba, el Orquestador extrae la `final_answer` y la registra en el `SessionState`. La API la expone en `GET /sessions/{id}`.  
**Salida:** Respuesta clara y verificable para el usuario  

---

## Diagrama del Flujo

```
Usuario
  │
  ▼
[API: Percepción]
  │
  ▼
[Orquestador] ──────────────────────────────────────────┐
  │                                                       │
  ▼                                                       │
[Analista: Interpretación] ─── goal, success_criteria    │
  │                                                       │
  ▼                                                       │
[Estratega: Planificación] ─── plan con dependencias     │
  │                                                       │
  ▼                                                       │
[Ejecutor × N tareas] ─── herramientas reales            │
  │                                                       │
  ▼                                                       │
[NCM: Observación] ─── CoherenceScore, anomalías         │
  │                                                       │
  ▼                                                       │
[Evaluador: Evaluación] ─── veredicto                    │
  │                                                       │
  ├── APPROVED ──────────────────────────────────────────┤
  │                                                       │
  └── NEEDS_CORRECTION / REJECTED ─── replanifica ───────┘
                                   (máx. max_iterations)
  │
  ▼
[Entrega al Usuario]
```

---

## Qué NO es Cognición

Aclaración filosófica importante:  
Los agentes no "piensan", no tienen "intenciones" ni "comprensión" en sentido fenomenológico. Lo que se implementa es un **proceso computacional de transformación de representaciones**: cada agente transforma un mensaje de entrada en un mensaje de salida usando un modelo de lenguaje como función de transformación. La "inteligencia" emerge de la composición de estas transformaciones y del protocolo de verificación.
