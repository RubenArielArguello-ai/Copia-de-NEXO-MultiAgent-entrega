# Guía para presentar y defender NEXO

## Presentación breve

«NEXO recibe una solicitud técnica y la procesa con cuatro agentes especializados. El Analista define el problema y criterios verificables, el Estratega crea un plan dependiente, el Ejecutor obtiene datos con herramientas controladas y el Evaluador decide si la evidencia cumple. El Orquestador conserva el contexto, controla las correcciones y persiste la trazabilidad. El NCM observa coherencia, pero no sustituye al Evaluador. El sistema puede usar Ollama local o mocks para pruebas.»

El guion ampliado de 18 diapositivas, la misión y las preguntas con respuestas están en [GUION_PRESENTACION.md](GUION_PRESENTACION.md). La presentación final editable es [NEXO_FINAL.pptx](../../NEXO_FINAL.pptx).

## Demostración sugerida

1. Mostrar `/models` y diferenciar disponibilidad de una prueba de inferencia.
2. Enviar una consulta de diagnóstico a la API.
3. Mostrar estado, plan, mensajes, herramienta ejecutada y evento NCM.
4. Explicar el veredicto y señalar `approved`, separado de `status`.
5. Mostrar la suite de tests y aclarar cuáles usan mocks.

## Preguntas frecuentes

**¿Por qué hay cuatro agentes?** Cada prompt y contrato limita la tarea: analizar, planificar, obtener evidencia y evaluar. La especialización permite inspeccionar el intercambio.

**¿El Orquestador también usa un modelo?** La configuración reserva un rol para él, pero el flujo implementado es lógica Python: coordina estados y mensajes de manera explícita.

**¿Cómo se evita que los agentes inventen el resultado?** Las herramientas devuelven datos; el prompt exige interpretarlos y el Evaluador recibe evidencia. Aun así, la decisión sigue siendo probabilística cuando usa un LLM y debe considerarse junto con los datos observables.

**¿Qué significa que una sesión sea `COMPLETED`?** Que terminó el pipeline. Solo `approved: true` confirma que el Evaluador devolvió `APPROVED`.

**¿Qué hace NCM?** Calcula señales de coherencia del plan y mensajes. No demuestra que el resultado técnico sea correcto.

**¿Para qué se usa `MockProvider`?** Para probar flujo y contratos sin servicio externo. Sus salidas fijas no prueban calidad del modelo ni de Ollama.

**¿Qué pasa si el Evaluador rechaza?** El Orquestador agrega correcciones del veredicto, pide replanificación y vuelve a intentar dentro de los límites configurados.

**¿La memoria garantiza una solución correcta?** No. Recupera experiencias parecidas; la evidencia actual debe validarse independientemente.

**¿Qué limitaciones tiene?** El bus coordina dentro de un proceso, la estrategia de selección de herramientas históricas usa palabras clave y el modelo puede generar JSON inválido. La ruta LangChain directa tiene más permisos que el ToolRegistry de diagnósticos.

## Conceptos que conviene dominar

Funciones/clases, JSON y enums en Python; API HTTP y códigos de respuesta; prompts, tokens y variabilidad LLM; grafos de dependencias; diferencia entre datos observados e interpretación; SQLite frente a búsqueda vectorial; pruebas unitarias con mocks; límites de seguridad de herramientas.
