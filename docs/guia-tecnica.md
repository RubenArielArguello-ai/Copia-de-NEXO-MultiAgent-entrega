# Guía técnica y educativa de NEXO

Esta guía apunta a la documentación de entrega vigente. El backend FastAPI y el Dashboard web, junto con Streamlit, consumen el mismo pipeline y la configuración central de modelos.

## Ejecutar

1. Iniciar Ollama y verificar los modelos configurados con `ollama list`.
2. Instalar dependencias con `python3 -m pip install -r requirements.txt`.
3. Iniciar la API: `uvicorn api.main:app --reload --host 127.0.0.1 --port 8000`.
4. Abrir `http://127.0.0.1:8000`; para la vista Streamlit complementaria ejecutar `streamlit run app.py`.

Streamlit usa `NEXO_API_URL` para apuntar a otra dirección API. Ambas interfaces presentan la misión y sus trazas a través de los endpoints de FastAPI.

## Recorrer el código

- Entrada HTTP y endpoints: `api/main.py`.
- Ciclo y fases: `nexo/core/orchestrator.py`.
- Contratos y agentes: `nexo/schemas/message.py`, `nexo/agents/`.
- Proveedores y modelos centrales: `nexo/providers/base_provider.py`, `nexo/config.py`.
- Herramientas autorizadas: `nexo/tools/`.
- Persistencia: `nexo/core/message_bus.py` (SQLite), `nexo/core/memory.py` (Chroma).
- Integración Streamlit: `app.py`; Dashboard web: `frontend/`.

## Documentación de aprendizaje

Leé en este orden: [Arquitectura](../ARQUITECTURA.md), [Agentes](../AGENTES.md), [Funciones](../FUNCIONES.md), [Flujo](../FLUJO_DE_EJECUCION.md), [Tecnologías](../TECNOLOGIAS.md), [Diagramas](../DIAGRAMA.md) y [Guía de defensa](../GUIA_PRESENTACION.md). La verificación ejecutada está registrada en [Informe final](../INFORME_FINAL.md).

## Límites importantes

`COMPLETED` indica que el pipeline finalizó; solo `approved: true` indica que el Evaluador aprobó. Ollama debe estar disponible para la inferencia real; los mocks son explícitos y se usan para pruebas. El pipeline solo afirma operaciones que una herramienta observó. Docker Compose se configuró, pero esta entrega validó configuración, no un build de imagen.
