# NEXO — Decisiones Técnicas (Architecture Decision Records)

Registro de decisiones de diseño relevantes. Para cada decisión se documenta el contexto, las opciones consideradas, la opción elegida y la justificación.

---

## ADR-001: Lenguaje y runtime

**Decisión:** Python 3.10+  
**Opciones:** Python, Node.js, Go  
**Justificación:** Python es el estándar de facto en IA/ML. El ecosistema de integración con Ollama, SQLite y FastAPI es maduro. El profesor lo conoce.

---

## ADR-002: Proveedor de LLM

**Decisión:** Interfaz `BaseLLMProvider` con implementaciones `OllamaProvider` y `MockProvider`  
**Opciones:** Hardcodear Ollama, usar LangChain, usar liteLLM  
**Justificación:** La abstracción permite cambiar de modelo sin modificar los agentes. No depende de frameworks externos. `MockProvider` permite CI sin Ollama.

---

## ADR-003: Modelos por agente

**Decisión:**
- Analista, Estratega, Evaluador, Orquestador → `gemma4:12b-mlx`
- Ejecutor → `qwen2.5-coder:7b`

**Justificación:** `gemma4:12b-mlx` es más rápido en Mac con MLX. `qwen2.5-coder:7b` es especializado en razonamiento técnico y diagnóstico, apropiado para el Ejecutor que interpreta resultados de herramientas.

---

## ADR-004: Comunicación inter-agente

**Decisión:** Message bus in-process con cola `deque` + persistencia SQLite  
**Opciones:** Redis, RabbitMQ, llamadas directas  
**Justificación:** Para un prototipo académico, in-process es suficiente y eliminamos la dependencia de infraestructura externa. SQLite provee trazabilidad sin complejidad operativa.

---

## ADR-005: Protocolo de mensajes

**Decisión:** Dataclass `NexoMessage` con campos `msg_id`, `from_agent`, `to_agent`, `task_id`, `goal`, `phase`, `payload`, `evidence`, `status`, `next_action`, `coherence_flags`, `timestamp`, `iteration`  
**Justificación:** Cumple exactamente el protocolo requerido por la consigna. Es serializable a JSON nativamente. Los `coherence_flags` permiten que el NCM anote mensajes sin modificar su contenido.

---

## ADR-006: Herramienta propia

**Decisión:** NEXO-Coherence Monitor con similitud de Jaccard  
**Opciones:** Cosine similarity con sentence-transformers, regex patterns, LLM-as-judge  
**Justificación:** Jaccard no requiere GPU ni modelos adicionales. Es completamente interpretable y auditable. La limitación (sensibilidad a sinónimos) está documentada como trabajo futuro.

---

## ADR-007: Similitud semántica sin GPU

**Decisión:** Tokenización por regex + stop words + Jaccard  
**Opciones:** TF-IDF, BM25, sentence-transformers  
**Justificación:** Zero dependencies extras. Funciona en cualquier Mac sin GPU. El umbral `DUPLICATION_THRESHOLD = 0.60` fue calibrado con casos de prueba para detectar solapamiento de al menos 3 de 4 términos clave.

---

## ADR-008: Framework web

**Decisión:** FastAPI + HTML/CSS/JS vanilla  
**Opciones:** Django, Flask, Next.js, React  
**Justificación:** FastAPI provee async, OpenAPI automático y es ligero. El frontend vanilla no requiere build step ni npm — el profesor puede inspeccionarlo directamente.

---

## ADR-009: Persistencia

**Decisión:** SQLite vía `sqlite3` estándar de Python  
**Opciones:** PostgreSQL, MongoDB, archivos JSON  
**Justificación:** Sin dependencias externas. Portable. El archivo `nexo_data.db` puede ser inspeccionado con cualquier cliente SQLite.

---

## ADR-010: Límite de iteraciones

**Decisión:** `max_iterations = 5`, `max_replanning_cycles = 2`  
**Justificación:** Evita ciclos infinitos. Para el caso de estudio académico, 5 iteraciones son más que suficientes. Configurable en `nexo/config.py`.

---

## ADR-011: Ejecución de herramienta real

**Decisión:** La `NetworkDiagnosticTool` ejecuta comandos reales del sistema operativo  
**Opciones:** Simular resultados, usar APIs externas  
**Justificación:** El profesor requiere una herramienta real. Los resultados reflejan el estado real del sistema donde se ejecuta NEXO. Esto hace la demo más convincente y el sistema más honesto.

---

## Decisiones Pendientes (a tomar en iteraciones futuras)

| ID | Decisión pendiente | Impacto |
|---|---|---|
| ADR-012 | Esquema de autenticación para la API | Bajo (académico) |
| ADR-013 | Estrategia de embedding para NCM v2 | Alto (mejora NCM) |
| ADR-014 | Comparativa cuantitativa con 50+ sesiones | Medio (evaluación) |
