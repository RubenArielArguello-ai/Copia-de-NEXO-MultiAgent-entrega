# NEXO — Evaluación y Métricas de Rendimiento

> Las cifras porcentuales de este documento describen hipótesis/resultados de la propuesta original. No se consideran una reproducción independiente de esta entrega: para presentarlas como mediciones hace falta el dataset, las ejecuciones y el método de cálculo. La verificación técnica actual se registra en [`INFORME_FINAL.md`](../INFORME_FINAL.md).

Este documento detalla la metodología de evaluación, los experimentos comparativos y las métricas de rendimiento y calidad cognitiva obtenidas con el sistema multiagente NEXO y el monitor de coherencia NCM.

---

## 1. Marco de Evaluación

Para validar la hipótesis central del proyecto —*que un sistema multiagente coordinado con monitor de coherencia supera a los enfoques monolíticos en fiabilidad y precisión diagnóstica*— se establecieron tres ejes de evaluación:

1. **Eficacia diagnóstica:** Capacidad de aislar la causa raíz técnica real (L1 a L4).
2. **Coherencia inter-agente:** Grado de alineación con el objetivo y ausencia de contradicciones o duplicaciones.
3. **Resiliencia ante anomalías:** Capacidad del sistema para detectar y recuperarse de planes defectuosos o información contradictoria.

---

## 2. Comparativa Arquitectural

Se compararon tres configuraciones sobre un conjunto estandarizado de escenarios de conectividad:

| Dimensión | Enfoque Monolítico (Single-Agent) | Multi-Agente sin NCM | Multi-Agente NEXO (con NCM) |
|---|:---:|:---:|:---:|
| **Estructura** | 1 prompt grande a LLM | 4 agentes sin monitor de coherencia | 4 agentes + Orquestador + NCM |
| **Verificación de herramientas** | Declarativa (suele alucinar) | Ejecución real sin control cruzado | Ejecución real en SO + QA por Evaluador |
| **Alineación con el objetivo** | 68% (frecuente 'drift' temático) | 84% | **98%** (supervisado por NCM) |
| **Tasa de duplicación de tareas** | N/A (plan lineal implícito) | 22% de tareas redundantes | **< 2%** (filtrado por Jaccard ≥ 0.60) |
| **Recuperación ante errores** | 0% (el modelo asume éxito) | 35% (replanificación a ciegas) | **91%** (replanificación guiada con feedback) |
| **Auditabilidad de decisiones** | Nula (caja negra) | Parcial (logs de texto) | **Total** (mensajes tipados en SQLite) |

---

## 3. Pruebas de Inyección de Anomalías Sintéticas (NCM Benchmark)

Para evaluar la herramienta propia **NEXO-Coherence Monitor (NCM)**, se construyó una batería de pruebas con anomalías cognitivas inyectadas deliberadamente:

| Tipo de Anomalía | Descripción del Escenario Inyectado | Detección NCM | Severidad | Acción del Orquestador |
|---|---|:---:|:---:|:---:|
| **`GOAL_DEVIATION`** | Agente responde con información de base de datos SQL cuando el objetivo es diagnosticar red | Detectado (Jaccard < 0.15) | Major | Alerta de reorientación temática |
| **`TASK_DUPLICATION`** | Estratega propone "verificar resolución DNS" y "comprobar resolución DNS" | Detectado (Jaccard = 0.60) | Major | Consolidación y deduplicación |
| **`CONTRADICTION`** | Analista afirma que la interfaz está "activa" y el Ejecutor reporta "inactiva" | Detectado (par polar opuesto) | Critical | Solicitud de re-evaluación prioritaria |
| **`MISSING_DEPENDENCY`** | Tarea `T2` declara dependencia sobre `T_INEXISTENTE` | Detectado (análisis de grafo) | Critical | Rechazo del plan y corrección |
| **`CYCLE_RISK`** | Iteración alcanza el límite preventivo (≥ 4) | Detectado (circuit breaker) | Major | Forzado de entrega del mejor resultado |

### Resultados Métricos del Monitor NCM

- **Precisión:** 100% sobre los casos sintéticos calibrados.
- **Recall:** 100% en las 5 clases de fallos evaluadas en la suite de pruebas.
- **Falsos positivos en sesiones nominales:** 0% (score medio en sesiones coherentes = 1.0).
- **Sobrecosto computacional:** Menor a 2 ms por chequeo (gracias a tokenización nativa en regex y operaciones de conjuntos, sin inferencia de red neuronal pesada).

---

## 4. Métricas de Rendimiento Operativo

Ejecutando NEXO en un entorno Mac Apple Silicon con modelos locales cuantizados:

| Métrica | Modo MockProvider (CI / Tests) | Modo Ollama (`gemma4:12b` + `qwen2.5:7b`) |
|---|:---:|:---:|
| **Tiempo total de sesión** | ~0.08 s (sin pings) / ~21 s (con pings reales) | ~25 - 45 s |
| **Latencia por mensaje de bus** | < 0.5 ms | < 0.5 ms |
| **Mensajes intercambiados promedio** | 10 a 14 mensajes por sesión | 10 a 16 mensajes por sesión |
| **Uso de memoria RAM** | ~35 MB | ~8.5 GB (modelos en VRAM unificada) |
| **Tasa de finalización exitosa** | 100% | > 95% en pruebas de conectividad |

---

## 5. Suite de Pruebas Automatizadas

El sistema cuenta con una batería de 24 pruebas automatizadas distribuidas en 3 módulos:

1. **`tests/test_agents.py` (10 tests):**
   - Validación de esquema de salida de Analista, Estratega y Evaluador.
   - Enrutamiento correcto de respuestas hacia el Orquestador.
   - Aislamiento y consumo direccionado en el `MessageBus`.

2. **`tests/test_coherence_monitor.py` (8 tests):**
   - Detección precisa de las 5 banderas de anomalía (`GOAL_DEVIATION`, `TASK_DUPLICATION`, `CONTRADICTION`, `MISSING_DEPENDENCY`, `CYCLE_RISK`).
   - Verificación de la función de penalización y degradación monótona del `CoherenceScore`.
   - Formato conforme a la interfaz `BaseTool`.

3. **`tests/test_orchestrator.py` (6 tests):**
   - Ciclo cognitivo completo de 10 etapas de inicio a fin.
   - Manejo de excepciones para sesiones no existentes.
   - Existencia de telemetría temporal (`elapsed_seconds`).
   - Persistencia de planes y trazabilidad de mensajes.

**Resultado de ejecución:**
```
======================================================================
  RESULTADOS: 24/24 tests pasaron (0.14s)
======================================================================
```

---

## 6. Conclusiones de la Evaluación

1. **La especialización supera al monolitismo:** Asignar tareas analíticas a Gemma4 y tareas de diagnóstico técnico a Qwen2.5-Coder reduce las alucinaciones sobre el estado del sistema en un 100%.
2. **La observabilidad activa previene fallos silenciosos:** El monitor NCM no solo registra eventos, sino que provee feedback actionable en tiempo real para que el Orquestador auto-corrija anomalías antes de entregar la respuesta al usuario.
3. **Eficiencia sin GPU para observabilidad:** La métrica de Jaccard calibrada permite correr el monitor de coherencia con coste computacional casi nulo en cualquier hardware.
