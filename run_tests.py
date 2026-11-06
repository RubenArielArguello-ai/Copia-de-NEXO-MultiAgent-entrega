#!/usr/bin/env python3
"""
NEXO — Test Runner.

Descubre y ejecuta todos los tests automatizados del sistema NEXO
sin requerir dependencias externas obligatorias (funciona tanto con pytest
como con el runtime estándar de Python).

Uso:
    python run_tests.py
    # o si pytest está instalado:
    python -m pytest tests/ -v
"""

import sys
import os
import time
import inspect
import importlib
from pathlib import Path

# Asegurar que el directorio raíz está en el PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

# Intentar usar pytest si está instalado y no se fuerza el runner nativo
USE_PYTEST = False
if "--native" not in sys.argv:
    try:
        import pytest
        USE_PYTEST = True
    except ImportError:
        USE_PYTEST = False


def run_with_pytest() -> int:
    import pytest
    args = ["tests", "-v"] + [arg for arg in sys.argv[1:] if arg != "--native"]
    return pytest.main(args)


def run_native() -> int:
    print("=" * 70)
    print("  NEXO — Test Runner Autónomo")
    print("=" * 70)

    tests_dir = ROOT_DIR / "tests"
    test_files = sorted(tests_dir.glob("test_*.py"))

    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    errors = []

    start_total = time.time()

    for file_path in test_files:
        module_name = f"tests.{file_path.stem}"
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            print(f"\n❌ Error al importar {module_name}: {e}")
            errors.append((module_name, str(e)))
            continue

        print(f"\n📁 {file_path.name}")

        # Buscar clases de test y funciones de test
        for attr_name in dir(module):
            attr = getattr(module, attr_name)

            # Clases que empiezan con Test
            if isinstance(attr, type) and attr_name.startswith("Test"):
                test_methods = [
                    m for m in dir(attr)
                    if m.startswith("test_") and callable(getattr(attr, m))
                ]
                for method_name in sorted(test_methods):
                    total_tests += 1
                    instance = attr()
                    t0 = time.time()
                    try:
                        # Setup si existe
                        if hasattr(instance, "setup_method"):
                            instance.setup_method()
                        elif hasattr(instance, "setUp"):
                            instance.setUp()

                        method = getattr(instance, method_name)
                        method()

                        # Teardown si existe
                        if hasattr(instance, "teardown_method"):
                            instance.teardown_method()
                        elif hasattr(instance, "tearDown"):
                            instance.tearDown()

                        dt = time.time() - t0
                        passed_tests += 1
                        print(f"  ✓ {attr_name}.{method_name} ({dt:.3f}s)")
                    except Exception as e:
                        dt = time.time() - t0
                        failed_tests += 1
                        print(f"  ✗ {attr_name}.{method_name} ({dt:.3f}s)")
                        errors.append((f"{attr_name}.{method_name}", str(e)))

            # Funciones sueltas test_*
            elif inspect.isfunction(attr) and attr_name.startswith("test_"):
                total_tests += 1
                t0 = time.time()
                try:
                    attr()
                    dt = time.time() - t0
                    passed_tests += 1
                    print(f"  ✓ {attr_name} ({dt:.3f}s)")
                except Exception as e:
                    dt = time.time() - t0
                    failed_tests += 1
                    print(f"  ✗ {attr_name} ({dt:.3f}s)")
                    errors.append((attr_name, str(e)))

    total_time = time.time() - start_total

    print("\n" + "=" * 70)
    print(f"  RESULTADOS: {passed_tests}/{total_tests} tests pasaron ({total_time:.2f}s)")
    if errors:
        print(f"  FALLOS: {len(errors)}")
        for name, err in errors:
            print(f"    - {name}: {err}")
    print("=" * 70)

    return 0 if failed_tests == 0 else 1


if __name__ == "__main__":
    if USE_PYTEST:
        sys.exit(run_with_pytest())
    else:
        sys.exit(run_native())
