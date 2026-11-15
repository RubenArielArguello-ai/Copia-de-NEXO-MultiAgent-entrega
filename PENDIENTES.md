# Pendientes y límites operativos reales

Este documento reemplaza los estados de entrega previos. No declara completo lo que depende de entorno externo o todavía no está implementado.

## Límites que siguen abiertos

- **Ejecución paralela:** las tareas corren secuencialmente. El MessageBus, los estados del agente y los presupuestos todavía no aíslan ejecuciones concurrentes.
- **Aislamiento fuerte de herramientas:** los límites de herramientas son cooperativos. El timeout del wrapper devuelve control y evita reentradas, pero no puede finalizar un hilo Python nativo que ya bloqueó dentro de una llamada del sistema.
- **Researcher:** sintetiza datos de la misión; no hace navegación web ni recopila fuentes externas. No se le presenta como buscador conectado.
- **Ingeniería de código:** análisis estático solamente. No modifica código ni ejecuta automáticamente suites arbitrarias.
- **Integraciones externas:** solo se declaran conectadas tras disponer de endpoints y credenciales válidas. No hay secretos de proveedor en el repositorio.
- **Memoria:** Chroma requiere almacenamiento persistente y Ollama `nomic-embed-text`. No hay todavía una API de retención/borrado por usuario ni políticas de TTL.
- **Docker/Ollama:** Compose conecta servicios, pero el operador debe descargar los modelos configurados en el volumen de Ollama antes de ejecutar misiones. `docker compose config` se valida; una imagen no se debe considerar probada si no se construye y ejecuta en el host destino.
- **Aviso Python 3.14:** LangSmith 0.14.17 emite deprecaciones por `asyncio.iscoroutinefunction`; `pip check` no detecta dependencias rotas. La advertencia proviene de la dependencia instalada y no se oculta.
- **Interacción humana para cambios sensibles:** las capacidades actualmente expuestas son diagnóstico y escritura limitada al workspace. No se exponen operaciones destructivas o administrativas para pedir confirmación.

## Verificación requerida antes de despliegue

1. Configurar `NEXO_API_TOKEN`, CORS y modelos dentro del entorno privado de despliegue.
2. Instalar en Ollama cada modelo indicado por las variables de entorno y, si se habilita memoria, el modelo de embeddings.
3. Ejecutar pruebas de carga y retención en el hardware y almacenamiento de producción.
4. Construir y levantar Compose en el host de destino; el test de configuración no reemplaza una prueba de runtime del contenedor.

No hay evidencia en este archivo de que esas verificaciones se hayan ejecutado fuera del entorno de desarrollo actual.
