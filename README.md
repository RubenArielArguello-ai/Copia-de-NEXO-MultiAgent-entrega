# NEXO — Sistema Cognitivo Multiagente

> Sistema multiagente para diagnóstico y resolución de problemas técnicos, construido como prototipo académico para una Diplomatura en Inteligencia Artificial.

---

## Qué es NEXO

NEXO es un **proveedor inteligente de servicios técnicos** implementado como sistema multiagente cognitivo. No es un chatbot. Es un sistema donde cuatro agentes especializados colaboran bajo la dirección de un orquestador para resolver solicitudes de forma razonada, planificada y verificable.

### Agentes

| Agente | Skill | Modelo |
|---|---|---|
| **Orquestador** | Coordinación y control del objetivo global | gemma4:12b-mlx |
| **Analista** | Interpretación y análisis del problema | gemma4:12b-mlx |
| **Estratega** | Planificación y descomposición en subtareas | gemma4:12b-mlx |
| **Ejecutor** | Ejecución de herramientas y diagnóstico técnico | qwen2.5-coder:7b |
| **Evaluador** | Verificación, QA y control de calidad | gemma4:12b-mlx |

### Herramienta Propia

**NEXO-Coherence Monitor (NCM)**: detecta anomalías cognitivas en la colaboración inter-agente:
- Desviación del objetivo original
- Duplicación semántica de tareas
- Contradicciones entre agentes
- Dependencias incumplidas
- Riesgo de ciclo infinito

---

## Requisitos

- Python 3.10+
- Ollama corriendo localmente con `gemma4:12b-mlx` y `qwen2.5-coder:7b`
- (Opcional) Los tests no requieren Ollama — usan MockProvider

```bash
# Verificar Ollama
ollama list
```

---

## Instalación

```bash
cd /Users/rubenarielarguello/Desktop/NEXO-MultiAgent

# Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

---

## Ejecución

### Demo en consola (sin servidor)

```bash
source .venv/bin/activate
python examples/internet_connectivity.py
```

### Servidor API + Dashboard

```bash
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000
# Abrir http://localhost:8000 en el navegador
```

### Tests automatizados

```bash
# Con el test runner integrado (sin dependencias adicionales):
python run_tests.py

# O con pytest en el entorno virtual:
source .venv/bin/activate
python -m pytest tests/ -v
```

---

## Proceso Cognitivo

```
Usuario → [Percepción] → Analista → [Interpretación]
        → Estratega → [Planificación]
        → Orquestador → [Distribución]
        → Ejecutor → [Acción + Herramientas]
        → NCM → [Observación + Coherencia]
        → Evaluador → [Evaluación]
        → [¿OK?] → Entrega
              ↘ [No] → Corrección → Orquestador (hasta max_iterations)
```

---

## Estructura del Proyecto

```
NEXO-MultiAgent/
├── nexo/
│   ├── core/           # Orquestador, bus de mensajes, estado
│   ├── agents/         # Analista, Estratega, Ejecutor, Evaluador
│   ├── tools/          # Diagnóstico de red + NCM (herramienta propia)
│   ├── providers/      # Ollama + Mock (intercambiables)
│   ├── schemas/        # Protocolo de mensajes
│   └── config.py       # Configuración central de modelos
├── api/                # FastAPI REST backend
├── frontend/           # Dashboard HTML/CSS/JS
├── tests/              # Tests automatizados
├── docs/               # Documentación completa
└── examples/           # Demo de ejecución
```

---

## Configurar modelos

Editar `nexo/config.py`:

```python
PROVIDER_CONFIG = {
    "ANALYST":    {"type": "ollama", "model": "gemma4:12b-mlx"},
    "EXECUTOR":   {"type": "ollama", "model": "qwen2.5-coder:7b"},
    # ...
}
```

Para usar mock (sin Ollama): `{"type": "mock"}`

---

## Documentación

- [`docs/vision.md`](docs/vision.md) — Visión del proyecto
- [`docs/architecture.md`](docs/architecture.md) — Arquitectura técnica
- [`docs/cognitive-process.md`](docs/cognitive-process.md) — Proceso cognitivo
- [`docs/innovation.md`](docs/innovation.md) — Herramienta propia (NCM)
- [`docs/evaluation.md`](docs/evaluation.md) — Métricas y pruebas

---

## Decisiones técnicas clave

Ver [`decisions.md`](decisions.md) para el registro completo de decisiones de arquitectura.
