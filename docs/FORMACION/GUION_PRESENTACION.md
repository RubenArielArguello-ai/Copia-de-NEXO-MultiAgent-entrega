# Guion de defensa y preguntas técnicas

## Guion por diapositiva

1. **Portada.** “NEXO es un prototipo multiagente que procesa solicitudes técnicas con un ciclo explícito y trazable.”
2. **Problema.** “Una respuesta directa mezcla interpretación, acción y control. Separar roles permite ver dónde aparece un error.”
3. **Objetivos.** “Buscamos delegación, herramientas con evidencia, persistencia y un límite seguro de iteraciones.”
4. **Arquitectura.** “El cliente usa FastAPI. El orquestador instancia los cuatro agentes y conecta SQLite, Chroma y Ollama.” Señalar las flechas como etapas del flujo.
5. **Tecnologías.** “Python es el backend; FastAPI expone HTTP; el navegador presenta datos. Streamlit queda como UI Python complementaria.”
6. **Modelos.** “Gemma se asigna a análisis, estrategia y evaluación; Qwen Coder al Ejecutor; nomic-embed-text a embeddings. Ollama corre localmente.” Mostrar `/models` para disponibilidad; disponibilidad no equivale a calidad.
7. **Agentes.** Explicar cada responsabilidad y distinguir a los agentes del orquestador, que aplica reglas de coordinación.
8. **Comunicación.** “El bus registra remitente, destino, fase, estado y carga útil. Los máximos de iteración y replanning cortan ciclos.”
9. **Memoria.** “SQLite es historial estructurado; Chroma es búsqueda vectorial. Solo guardamos resultados aprobados; recuperar memoria orienta, no demuestra.”
10. **Herramientas.** Mostrar el registro de herramientas de diagnóstico. Explicar que la ejecución Python/archivos es la ruta LangChain complementaria y requiere permisos controlados.
11. **Dashboard.** Iniciar una solicitud; mostrar agentes/modelos, plan, mensajes, memoria, evaluación, historial y métricas recibidas de endpoints reales.
12. **Misión.** Enviar: “Usá la herramienta system_diagnostic para relevar el sistema y el espacio de disco disponible. Resume únicamente valores observados y advierte cualquier limitación.” Seguir análisis, plan, herramienta y evaluación.
13. **Resultados.** La corrida real local por API registrada el 13-11-2026 terminó `COMPLETED`, `approved: true`, `APPROVED`, 1 iteración, 8 mensajes y 43.60 s. `system_diagnostic` observó macOS Darwin 25.5.0 arm64, 10 CPU y disco 460.38 GB total / 439.32 GB usado / 21.06 GB libre (95.4%). La memoria Chroma guardó el resultado aprobado y una búsqueda semántica posterior recuperó el registro. Diferenciar esto de la integración con mocks; nunca presentar una prueba mock como inferencia real.
14. **Problemas y soluciones.** Explicar rechazo con límite de correcciones; evitar fallback silencioso; evitar embeddings si Chroma está vacío; conectar rutas del Dashboard a API.
15. **Conclusiones.** “COMPLETED indica que la ejecución terminó; `approved` indica el veredicto. El sistema hace observable el proceso, no vuelve infalible al modelo.”
16. **Futuro.** Proponer aislamiento de Python, autenticación, métricas por agente, evaluación sistemática y streaming.

## Preguntas técnicas posibles

**¿Qué es un agente autónomo aquí?** Un componente que recibe un objetivo acotado, usa un modelo y devuelve una salida contractual; el orquestador conserva el control del flujo.

**¿Por qué no usar un único agente?** La separación permite asignar instrucciones y evidencias distintas y auditar el origen de cada salida. Tiene costo de latencia y coordinación.

**¿Qué ocurre si el Evaluador rechaza?** El orquestador pasa problemas/correcciones a una replanificación, dentro de `NEXO_MAX_REPLANNING` y `NEXO_MAX_ITERATIONS`. Agotado el límite, termina sin aprobación.

**¿El resultado COMPLETED está aprobado?** No necesariamente. Hay que consultar `approved` o `verdict`; `COMPLETED` significa que el ciclo cerró.

**¿Cómo se evita guardar un resultado malo?** Solo la rama `APPROVED` llama a la persistencia de memoria y el modo mock omite esa escritura.

**¿Qué diferencia hay entre SQLite y Chroma?** SQLite consulta por sesión, estado y mensajes; Chroma busca textos por similitud vectorial.

**¿La coherencia NCM comprueba la verdad?** No. Calcula señales de consistencia entre plan y mensajes. La evaluación de evidencia y la herramienta son necesarias.

**¿Un modelo local elimina riesgos?** Reduce dependencia de API externa, pero no elimina errores, variabilidad ni riesgos de herramientas. Aislamiento y permisos siguen importando.

**¿Qué demuestra una prueba con MockProvider?** Contratos, control de flujo e integración de software; no demuestra inferencia ni calidad de Ollama.

**¿Qué puede mostrar `/models`?** Configuración y disponibilidad de tags locales. Una generación efectiva se demuestra con una llamada de inferencia o misión completa.

**¿Qué limita la solución?** Variabilidad del modelo, latencia, búsqueda de memoria dependiente del servicio embeddings, coordinación en proceso y el mayor riesgo de la ruta que ejecuta Python.

## Preparación antes de exponer

1. Verificar `ollama list` y confirmar Gemma, Qwen y `nomic-embed-text`.
2. Iniciar Ollama, luego API y abrir `http://localhost:8000`.
3. Mostrar estado de modelos y ejecutar la misión del punto 12.
4. Esperar el estado terminal y verificar `approved`; registrar también si acabó sin aprobación.
5. Mostrar plan, mensajes, resultado, historial y la segunda ejecución para observar recuperación si el primer resultado fue aprobado.
6. Consultar `INFORME_FINAL.md` para comunicar límites observados de la prueba.
