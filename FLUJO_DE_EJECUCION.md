# Flujo de ejecución

1. El Dashboard envía `POST /sessions` con el objetivo.
2. FastAPI crea un estado y ejecuta `_run_session`.
3. El Orquestador construye proveedores por rol y carga contexto de memoria si está disponible.
4. Analista devuelve interpretación y criterios. Si el JSON falla, se preserva el objetivo literal con criterios mínimos.
5. Estratega devuelve tareas. Si su formato falla, propone una acción mínima derivada del objetivo, todavía sujeta a resolución de herramienta.
6. El Orquestador filtra tareas sin herramienta conocida, normaliza dependencias y registra el plan.
7. Ejecutor llama herramienta. En crear-y-leer un archivo, son dos tareas: escribir y después leer el mismo archivo.
8. Cada resultado real se guarda; el modelo solo lo interpreta y no reemplaza los campos que provienen de la herramienta.
9. Evaluador revisa objetivo, criterios y resultados. Sin evidencia exitosa, un veredicto aprobado se transforma en rechazo.
10. Ante rechazo puede haber replanificación acotada por `NEXO_MAX_REPLANNING` y `NEXO_MAX_ITERATIONS`.
11. El resultado persiste en SQLite; memoria Chroma se escribe únicamente para aprobaciones reales.

El Dashboard consulta estado, mensajes, herramientas, coherencia, modelos, logs e historial. `COMPLETED` describe fin del ciclo; `approved` describe el veredicto.
