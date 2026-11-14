# Resumen técnico para defender NEXO

## Exposición breve

NEXO es un prototipo académico que resuelve misiones técnicas mediante cuatro agentes con roles distintos. El Analista interpreta el pedido y define qué cuenta como éxito; el Estratega lo transforma en un plan acotado; el Ejecutor llama herramientas registradas y devuelve observaciones; el Evaluador compara esas observaciones con el objetivo y decide si la evidencia alcanza. Un Orquestador escrito en Python coordina las etapas, mensajes, estado y reintentos. Los modelos de lenguaje se ejecutan localmente con Ollama.

FastAPI conecta el Dashboard web con el núcleo. SQLite conserva sesiones y trazas; Chroma permite recuperar resultados aprobados como contexto. Una memoria previa no demuestra el resultado de la misión actual: esa demostración depende de la salida observada de sus herramientas.

## Recorrido para explicar el sistema

1. Mostrar el flujo en [DIAGRAMA.md](DIAGRAMA.md) y señalar la API, el Orquestador y los cuatro agentes.
2. Separar roles/skills de herramientas: los primeros razonan sobre etapas; `ToolRegistry` valida y ejecuta capacidades concretas.
3. Explicar Ollama, el modelo predeterminado `qwen2.5-coder:7b` y los overrides por rol en `nexo/config.py`.
4. Presentar la evidencia ya aprobada: misión `ee0d35a4`, `COMPLETED` y `APPROVED`; `prueba_nexo_final.txt` fue escrito, leído y verificado. No repetir la misión como requisito para la defensa.
5. Aclarar que `COMPLETED` significa ciclo terminado y `APPROVED` significa que el Evaluador aceptó evidencia. Mencionar límites y aprendizaje.

## Guion para preguntas

**¿El Orquestador es otro agente LLM?** En el pipeline documentado, no: es coordinación determinista en Python. La inferencia corresponde a los cuatro agentes especializados.

**¿Qué diferencia hay entre una skill y una herramienta?** La skill/instrucción define la responsabilidad del agente. La herramienta es código registrado que realiza una operación concreta, como diagnóstico o lectura/escritura permitida.

**¿Cómo se demuestra que una misión fue aprobada?** Con el estado/veredicto del registro de misión y evidencia observada de ejecución. La misión de entrega terminó `COMPLETED / APPROVED`; el archivo fue leído después de escribirlo.

**¿Qué papel tiene el Evaluador?** Contrasta objetivo, criterios y resultados. El sistema impide aprobación cuando no hay ejecución exitosa o cuando la evidencia de archivo no coincide con el contenido solicitado.

**¿Qué aporta el monitor de coherencia?** Comprueba señales de desviación, duplicación, contradicción, dependencias y ciclos. Es una herramienta interna consultada por el Orquestador, no un agente adicional.

**¿Por qué modelos locales?** Ollama permite servir modelos sin enviar los prompts a un proveedor remoto. El endpoint y los modelos se configuran localmente; la latencia y la calidad dependen del hardware y del modelo.

**¿Qué queda limitado?** La selección de acciones está acotada por el registro y reglas; los modelos pueden producir errores; la ruta auxiliar LangChain que ejecuta Python conserva permisos del proceso; Docker no fue construido para esta entrega y el adaptador de Chroma requiere una migración futura.

## Archivos de apoyo

[README](README.md), [informe final](INFORME_FINAL.md), [agentes](AGENTES.md), [arquitectura](ARQUITECTURA.md), [flujo](FLUJO_DE_EJECUCION.md), [tecnologías](TECNOLOGIAS.md) y [presentación editable](NEXO_FINAL.pptx).
