# Pendientes NEXO
1. 7 tests fallan, 49 pasan. Son descuadres entre tests y código:
   - tests/test_config.py importa PROVIDER_CONFIG como variable, pero en nexo/core/config.py es un método.
   - ConfigManager no tiene el atributo max_iterations.
   - Orchestrator (nexo/core/orchestrator.py) no tiene start_mission, solo run().
2. La función de porcentaje de avance quedó en nexo/core/orchestador.py (con "ch"). Hay que moverla a orchestrator.py.
3. Borrar los duplicados nexo/core/orchestador.py y nexo/core/orquestador.py cuando todo pase.
4. La tarea de Dockerfile no hizo cambios. Hacerla a mano o con otro modelo.
