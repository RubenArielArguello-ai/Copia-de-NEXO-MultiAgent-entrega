# Informe de entrega — NEXO MultiAgent

## Descripción

NEXO es un prototipo académico de resolución de misiones técnicas con cuatro agentes LLM especializados y un Orquestador Python. La aplicación expone sesiones mediante FastAPI, presenta el estado en un Dashboard web y conserva mensajes y sesiones en SQLite. Chroma ofrece recuperación semántica de resultados aprobados.

## Implementación entregada

- **Orquestador:** crea los agentes, conduce análisis, planificación, ejecución y evaluación; limita iteraciones/replanificaciones y decide entrega o fallo. `CoherenceMonitor` acompaña el ciclo con comprobaciones de coherencia.
- **Analista:** produce interpretación, restricciones y criterios de éxito.
- **Estratega:** descompone la misión en acciones acotadas y dependencias.
- **Ejecutor:** selecciona herramientas disponibles y conserva sus resultados como evidencia.
- **Evaluador:** aplica un veredicto y rechaza resultados sin evidencia de ejecución satisfactoria.
- **Herramientas:** `ToolRegistry` registra capacidades técnicas delimitadas. Las skills son instrucciones y responsabilidades de agentes; no ejecutan acciones por sí solas.
- **Modelos:** Ollama local es el proveedor predeterminado. Los cuatro roles usan `qwen2.5-coder:7b` por defecto y admiten configuración independiente. `nomic-embed-text` genera embeddings para Chroma.

## Evidencia de la misión aprobada

La misión **`ee0d35a4`** terminó con estado **COMPLETED** y veredicto **APPROVED**. La operación solicitada sobre `prueba_nexo_final.txt` se escribió, se leyó y se verificó correctamente. El archivo conservado contiene `NEXO verificado por escritura y lectura`. Se documenta el resultado informado para esta entrega; no se repitió la misión ni se inspeccionó otra vez su sesión.

`COMPLETED` indica que el ciclo terminó; `APPROVED` indica que el Evaluador aceptó la evidencia. Son datos distintos y deben mostrarse juntos al explicar el resultado.

## Limitaciones pendientes

- La inferencia requiere que Ollama y los modelos estén disponibles en la máquina de demostración; la calidad depende del modelo.
- Los planes solo pueden ejecutar herramientas registradas y reconocidas. La evaluación automática puede cometer errores.
- La ruta auxiliar LangChain para ejecutar Python hereda permisos del proceso y no está aislada.
- No se construyó una imagen Docker para esta entrega.
- El adaptador Chroma actual emite una advertencia de deprecación; la migración queda para trabajo futuro.
- Los registros históricos sin procedencia verificable no deben atribuirse a Ollama ni a mocks.

## Archivos de presentación

El [README](README.md) funciona como entrada al proyecto. La explicación paso a paso está en [GUIA_PRESENTACION.md](GUIA_PRESENTACION.md); los detalles se amplían en [ARQUITECTURA.md](ARQUITECTURA.md), [AGENTES.md](AGENTES.md), [FUNCIONES.md](FUNCIONES.md), [FLUJO_DE_EJECUCION.md](FLUJO_DE_EJECUCION.md), [TECNOLOGIAS.md](TECNOLOGIAS.md) y [DIAGRAMA.md](DIAGRAMA.md). La presentación editable está en [NEXO_FINAL.pptx](NEXO_FINAL.pptx).

No se repitieron pruebas, no se reiniciaron servicios y no se eliminaron archivos ni cambios existentes durante este cierre documental.
