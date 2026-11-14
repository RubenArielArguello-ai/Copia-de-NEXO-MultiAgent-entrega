# Ruta de aprendizaje

1. Lee `nexo/schemas/message.py` para entender el contrato que comparten los agentes.
2. Sigue `BaseAgent.run()` y luego un `process()` de Analista para aprender el ciclo de un agente.
3. Lee `StateManager` y `MessageBus` para separar estado actual de trazabilidad persistente.
4. Recorre `Orchestrator.run()` y las funciones `_phase_*` para ver cómo se coordinan las fases y dependencias.
5. Inspecciona `ToolRegistry` y una herramienta concreta para entender validación, ejecución y errores.
6. Compara `OllamaProvider` con `MockProvider`; verifica disponibilidad en `/models` antes de una demo real.
7. Ejecuta `python -m pytest -q` y abre el test de orquestación para ver cómo inyectar proveedores falsos.
8. Compara la API (pipeline multiagente), el modo de equipo de Streamlit y el modo LangChain directo; tienen alcances diferentes.
9. Revisa `message_bus.py` y `memory.py` para comprender SQLite y Chroma, y cómo se diferencian.
10. Usa la guía de presentación para explicar límites, evidencia y los riesgos de la ejecución de código.

Los archivos esenciales y los contratos de las funciones están indexados en [FUNCIONES](FUNCIONES.md); el mapa completo del proyecto está en [docs/guia-tecnica.md](../guia-tecnica.md).
