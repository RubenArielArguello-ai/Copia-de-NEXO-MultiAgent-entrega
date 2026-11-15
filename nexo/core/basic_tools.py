"""Compatibilidad de herramientas heredadas sin caminos de ejecución inseguros.

Las implementaciones seguras viven en ``nexo.tools.basic_tools`` y restringen
las rutas al workspace y Python a expresiones aritméticas.
"""
from nexo.tools.basic_tools import (  # noqa: F401
    ejecutar_codigo_python,
    escribir_archivo,
    leer_archivo,
)
