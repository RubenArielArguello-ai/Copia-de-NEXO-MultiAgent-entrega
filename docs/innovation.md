# NEXO — Investigación de Herramienta Propia: NEXO-Coherence Monitor (NCM)

## 1. Herramientas Existentes Analizadas

### LangSmith (LangChain)
**Qué hace:** Plataforma de observabilidad para pipelines LLM. Rastrea llamadas, latencias, tokens usados y outputs.  
**Limitación relevante:** Es una herramienta de *instrumentación post-hoc*. Registra lo que pasó, pero no detecta en tiempo real si los agentes se están desviando del objetivo o contradiciendo entre sí.  

### Galileo AI
**Qué hace:** Monitoreo de calidad de outputs LLM: alucinaciones, relevancia, coherencia de respuesta individual.  
**Limitación relevante:** Evalúa respuestas individuales, no la *coherencia del grafo de mensajes entre múltiples agentes*.

### Phoenix (Arize)
**Qué hace:** Observabilidad de spans de razonamiento, visualización de embeddings, análisis de drift.  
**Limitación relevante:** Foco en distribución de datos y drift de modelos. No analiza contradicciones semánticas entre agentes ni duplicidad de tareas a nivel de plan.

### LangGraph
**Qué hace:** Framework de orquestación de agentes mediante grafos de estado. Permite definir flujos con nodos y edges.  
**Limitación relevante:** Provee estructura pero no *feedback semántico sobre la calidad de la colaboración*. Es un motor de ejecución, no un monitor cognitivo.

### AutoGen (Microsoft)
**Qué hace:** Framework multiagente con comunicación por turnos y logging de conversaciones.  
**Limitación relevante:** El logging es estructural (quién habló y cuándo), no semántico (si lo que dijeron es coherente con el objetivo).

---

## 2. Brecha Identificada

Ninguna herramienta existente combina las siguientes cuatro capacidades **en tiempo de ejecución** con criterio **semántico**:

| Capacidad | LangSmith | Galileo | Phoenix | LangGraph | **NCM** |
|---|:---:|:---:|:---:|:---:|:---:|
| Tracing de mensajes | ✓ | — | ✓ | ✓ | ✓ |
| Calidad de respuesta individual | — | ✓ | — | — | — |
| Desviación del objetivo global | — | — | — | — | ✓ |
| Duplicación semántica de tareas | — | — | — | — | ✓ |
| Contradicción entre agentes | — | — | — | — | ✓ |
| Dependencias incumplidas | — | — | — | — | ✓ |
| Riesgo de ciclo | — | — | — | Parcial | ✓ |
| **Alerta al Orquestador para replanificar** | — | — | — | — | ✓ |

---

## 3. Contribución Propia: NCM

### Definición

El **NEXO-Coherence Monitor** es una herramienta de verificación de coherencia colaborativa que analiza el grafo de mensajes de una sesión y emite alertas semánticas al Orquestador.

### Capacidades implementadas

**A. Detección de desviación del objetivo (GOAL_DEVIATION)**  
Calcula la similitud de Jaccard entre el objetivo original y los payloads de los mensajes recientes. Si la similitud es menor que el umbral `DEVIATION_THRESHOLD = 0.15`, el sistema alertó al Orquestador.

**B. Detección de duplicación de tareas (TASK_DUPLICATION)**  
Compara todas las descripciones de tareas del plan mediante similitud de Jaccard. Si dos tareas tienen similitud ≥ `DUPLICATION_THRESHOLD = 0.60`, se reporta como duplicación.

**C. Detección de contradicciones (CONTRADICTION)**  
Busca pares de palabras de polaridad opuesta en los payloads de mensajes de agentes diferentes: `(up, down)`, `(funciona, no funciona)`, `(activa, inactiva)`, etc.

**D. Dependencias incumplidas (MISSING_DEPENDENCY)**  
Verifica que todas las dependencias declaradas en el plan referencien tareas que existen.

**E. Riesgo de ciclo (detectado por iteración)**  
Si `iteration >= MAX_ITERATIONS_WARNING`, el NCM activa `cycle_risk = True`.

### CoherenceScore

```
score = 1.0 - Σ penalidades_por_anomalía
  penalty_critical = 0.30
  penalty_major    = 0.15
  penalty_minor    = 0.05
  penalty_cycle    = 0.20
```

Score ∈ [0.0, 1.0]. Score < 0.5 → replanificación automática.

---

## 4. Comparación con Alternativas

La técnica de Jaccard sobre tokens fue elegida por:
- **Sin dependencias:** No requiere sentence-transformers, GPU ni modelos adicionales
- **Interpretable:** El profesor puede entender y auditar la métrica
- **Extensible:** Se puede reemplazar por cosine similarity con embeddings si se instala `sentence-transformers`

La limitación es que la similitud de Jaccard es sensible al vocabulario. Un sistema que use sinónimos podría no ser detectado. Esto se documenta como trabajo futuro.

---

## 5. Prueba de Utilidad

Ver `docs/evaluation.md` para las métricas comparativas entre:
- Sistema single-agent (sin NCM)
- Sistema multiagente sin NCM
- Sistema multiagente con NCM

La prueba de utilidad del NCM consiste en inyectar anomalías sintéticas y verificar que el sistema:
1. Las detecta correctamente (tests en `tests/test_coherence_monitor.py`)
2. Desencadena replanificación cuando corresponde
3. No genera falsos positivos en sesiones coherentes

---

## 6. Trabajo Futuro

- Reemplazar Jaccard por cosine similarity con embeddings locales (`sentence-transformers`)
- Exportar el grafo de mensajes como archivo `.graphml` para visualización
- Comparativa cuantitativa publicada con 50+ sesiones reales
