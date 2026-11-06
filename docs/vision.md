# NEXO — Visión del Proyecto

## Propósito

NEXO nace con una premisa clara: demostrar que la inteligencia artificial aplicada a problemas reales no requiere un único modelo monolítico, sino un ecosistema de agentes especializados que razonan, colaboran y se corrigen mutuamente.

## Objetivo Académico

El proyecto responde a la consigna de una Diplomatura en Inteligencia Artificial:

> *Comprender qué es la IA, cómo se construyen agentes capaces de razonar, cómo colaboran y cómo se crean herramientas nuevas cuando las existentes no cubren una necesidad.*

NEXO no es un chatbot mejorado. Es un **sistema cognitivo distribuido** con arquitectura orquestador-agentes, comunicación estructurada y capacidad de autocorrección.

## Objetivo del Sistema

Recibir una solicitud de servicio técnico, comprenderla, planificar su resolución, ejecutar diagnósticos reales, evaluar los resultados contra el objetivo original y entregar una respuesta verificable — detectando y corrigiendo errores en el proceso.

## Caso de Estudio Principal

**"Mi computadora no se conecta a Internet."**

Este caso fue elegido porque:
1. Es un problema multicapa (física → red → DNS → aplicación)
2. Requiere diagnóstico secuencial con dependencias
3. Tiene criterios de éxito verificables (ping funciona, DNS resuelve)
4. Puede fallar de múltiples formas, forzando al sistema a replanificar
5. Es comprensible para cualquier audiencia

## Principios de Diseño

| Principio | Implementación |
|---|---|
| **Separación de responsabilidades** | Cada agente tiene un único skill |
| **Comunicación trazable** | Protocolo de mensajes estructurado con SQLite |
| **Autonomía controlada** | El Orquestador mantiene el objetivo; los agentes no deciden solos |
| **Corrección activa** | El Evaluador puede rechazar y el Orquestador replanifica |
| **Independencia del modelo** | Sistema funciona con Ollama, mock o cualquier LLM vía `BaseLLMProvider` |

## Lo que NEXO NO es

- No es una red neuronal
- No tiene "consciencia" ni "comprensión" en sentido filosófico
- No es un sistema de producción listo para despliegue empresarial
- No depende de APIs externas (funciona completamente local)

## Contribución Original

La herramienta **NEXO-Coherence Monitor (NCM)** es la contribución técnica propia del proyecto. Detecta anomalías cognitivas en la colaboración inter-agente que los sistemas de observabilidad existentes (LangSmith, Galileo, Phoenix) no analizan en tiempo de ejecución con criterio semántico.
