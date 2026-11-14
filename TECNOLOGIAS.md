# Tecnologías

- **Python:** agentes, coordinación, herramientas y lógica de persistencia.
- **FastAPI / Uvicorn:** API REST y servidor del frontend existente.
- **Streamlit:** segunda vista conectada por HTTP a FastAPI.
- **Ollama:** inferencia local; modelo predeterminado por agente definido en `nexo/config.py`.
- **SQLite:** sesiones, mensajes, herramientas y coherencia.
- **Chroma + nomic-embed-text:** memoria semántica persistente.
- **LangChain:** herramientas de la ruta directa y fábrica de modelos complementaria.
- **Docker Compose:** empaqueta API y Ollama con volúmenes persistentes.
- **HTML, CSS y JavaScript:** Dashboard web ya integrado con endpoints de la API.

Las librerías se declaran en `requirements.txt`. Ollama debe tener instalados los modelos configurados. `ollama list` solo confirma instalación; la disponibilidad de servicio se comprueba con `/models` y la inferencia real.

SQLite y Chroma tienen usos distintos: SQLite conserva eventos estructurados; Chroma recupera documentos similares por significado. Un recuerdo nunca reemplaza la evidencia de herramienta de la misión actual.
