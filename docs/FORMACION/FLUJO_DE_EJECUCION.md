# Flujo de ejecución de una misión

## Dashboard web y API

1. La persona escribe un objetivo en `frontend/index.html` y `frontend/app.js` envía `POST /sessions` con JSON `{ "request": "..." }`.
2. `create_session()` valida que el texto no esté vacío, crea un `SessionState` y agenda `_run_session()`.
3. `Orchestrator.run()` construye `MessageBus`, registra la sesión y crea agentes con su proveedor.
4. `_phase_analysis()` publica una solicitud al Analista. Este transforma texto a análisis JSON y responde.
5. `_phase_planning()` entrega análisis al Estratega. El plan contiene IDs, tareas, agente y dependencias.
6. En cada iteración, el NCM revisa el estado. `_phase_execution()` recorre el plan en orden; si faltan dependencias, marca la tarea fallida y la salta.
7. El Ejecutor deriva la subtarea a una herramienta registrada. El resultado se guarda en el historial y también se envía al modelo para interpretación.
8. `_phase_evaluation()` presenta objetivo original, criterios, plan y resultados al Evaluador.
9. `APPROVED` permite entregar. `NEEDS_CORRECTION` o `REJECTED` puede volver al Estratega con correcciones. Hay límites separados de iteraciones y replanificaciones.
10. La sesión se finaliza y persiste. El navegador consulta estado y mensajes; muestra aprobación por separado del estado terminal.

## Streamlit

La opción «Equipo multiagente» llama `ejecutar_mision_completa()` y muestra estado, veredicto, plan y métricas. La opción «Ejecutor con herramientas» llama `ejecutar_mision_directa()` y mantiene el ciclo independiente de tres intentos: orden al Ejecutor, texto de feedback del Evaluador y posible corrección. En esa ruta la aprobación se detecta por una etiqueta inicial exacta, de modo que `RECHAZADO` no coincide accidentalmente con `APROBADO`.

## Estados a interpretar correctamente

- `COMPLETED` significa que el ciclo terminó; el campo `approved` indica si el Evaluador aprobó el objetivo.
- `FAILED` indica error de ejecución del pipeline, no un simple rechazo de calidad.
- El mock devuelve fixtures predefinidos. Una sesión completada con mock demuestra integración de componentes, no exactitud de un modelo real.
- Si Ollama falta, el pipeline real falla con el mensaje del proveedor; solo una configuración deliberada `type: mock` usa fixtures. Consultá `/models` y los logs antes de presentar una ejecución como inferencia real.
