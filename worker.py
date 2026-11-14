import time
from nexo.core.llm_factory import get_llm_for_role
from nexo.agents.executor import crear_agente_ejecutor


def iniciar_trabajo_autonomo(objetivo_principal: str, config_dict: dict):
    print(f"🚀 [WORKER] Iniciando proyecto: {objetivo_principal}")

    # 1. Traemos al Ejecutor
    agente = crear_agente_ejecutor(config_dict)

    # 2. Creamos el estado inicial de la misión
    historial_tareas = []
    paso_actual = 1
    max_pasos = 4  # Límite para que no se vuelva loco

    contexto = f"OBJETIVO PRINCIPAL: {objetivo_principal}\n"

    while paso_actual <= max_pasos:
        print(f"\n🔄 [WORKER] --- INICIANDO PASO {paso_actual} ---")

        # Le pedimos al agente que piense en el SIGUIENTE paso lógico
        prompt_paso = (
            f"Estás trabajando en un proyecto autónomo.\n"
            f"{contexto}\n"
            f"Historial de lo que ya hiciste:\n{historial_tareas}\n\n"
            f"Tu tarea ahora es dar EL SIGUIENTE PASO lógico para avanzar. "
            f"Si el objetivo ya está 100% completado, responde exactamente con la palabra FINALIZADO. "
            f"De lo contrario, usa tus herramientas para hacer la siguiente parte del trabajo."
        )

        try:
            # El agente ejecuta la acción
            resultado = agente.invoke({"input": prompt_paso})
            respuesta_agente = resultado["output"]

            print(f"✅ [WORKER] Resultado del paso: {respuesta_agente[:150]}...")

            # Guardamos en el historial
            historial_tareas.append(f"Paso {paso_actual}: {respuesta_agente}")
            contexto += (
                f"\nLo que hiciste en el paso {paso_actual}: {respuesta_agente}\n"
            )

            # Verificamos si terminó
            if "FINALIZADO" in respuesta_agente.upper():
                print(
                    "\n🎉 [WORKER] ¡El agente ha indicado que el proyecto está terminado!"
                )
                break

        except Exception as e:
            print(f"❌ [WORKER] Error en el paso {paso_actual}: {e}")
            historial_tareas.append(f"Paso {paso_actual} falló: {e}")

        paso_actual += 1
        time.sleep(1)  # Pausa para no saturar la Mac

    print("\n🏁 [WORKER] Proceso finalizado.")
    print("Resumen de lo realizado:")
    for t in historial_tareas:
        print("-", t)


# --- PRUEBA DE FUEGO ---
if __name__ == "__main__":
    config = {"EXECUTOR": {"type": "ollama", "model": "qwen2.5-coder:7b"}}

    # Aquí le damos una tarea LARGA
    mision = (
        "Crea una mini calculadora en Python. "
        "1. Crea un archivo calculadora.py que tenga funciones para sumar y restar. "
        "2. Crea un archivo test_calculadora.py que importe esas funciones y las pruebe. "
        "3. Ejecuta el test para verificar que funciona."
    )

    iniciar_trabajo_autonomo(mision, config)
