"""
NEXO — Proveedores de modelos de lenguaje.

Interfaz abstracta + implementaciones para:
  - OllamaProvider: modelos locales vía Ollama HTTP API con reintentos y telemetría
  - MockProvider:   respuestas deterministas seleccionadas explícitamente para tests
"""

from __future__ import annotations
import json
import logging
import re
import time
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"


def clean_llm_output(text: str) -> str:
    """
    Limpia etiquetas de pensamiento (<thought>...</thought> o <think>...</think>)
    y espacios superfluos producidos por modelos tipo reasoning/thinking.
    Si el texto resultante queda vacío, conserva el texto original para no perder datos.
    """
    if not text:
        return ""
    cleaned = re.sub(r'<(?:thought|think)>.*?</(?:thought|think)>', '', text, flags=re.DOTALL).strip()
    return cleaned if cleaned else text.strip()


class BaseLLMProvider(ABC):
    """Interfaz común para todos los proveedores de LLM en NEXO."""

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """Genera una respuesta dado un prompt de sistema y uno de usuario."""

    @abstractmethod
    def is_available(self) -> bool:
        """Verifica si el proveedor está disponible."""


class OllamaProvider(BaseLLMProvider):
    """
    Proveedor para modelos locales vía Ollama.
    Usa la API HTTP de Ollama con control de reintentos, timeouts y telemetría.
    """

    def __init__(
        self,
        model: str,
        base_url: str = OLLAMA_BASE_URL,
        timeout: int = 120,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
    ):
        self.model          = model
        self.base_url       = base_url.rstrip("/")
        self.timeout        = timeout
        self.max_retries    = max(1, max_retries)
        self.backoff_factor = backoff_factor
        self.last_telemetry: dict[str, Any] = {}

    def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        Ejecuta la inferencia contra Ollama con reintentos controlados.
        """
        payload = {
            "model":  self.model,
            "stream": False,
            "messages": [
                {"role": "system",  "content": system_prompt},
                {"role": "user",    "content": user_prompt},
            ],
            "options": {
                "temperature": kwargs.get("temperature", 0.2),
                "num_predict": kwargs.get("max_tokens", 512),
            }
        }
        if kwargs.get("format") == "json":
            payload["format"] = "json"

        data = json.dumps(payload).encode("utf-8")
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            t0 = time.time()
            try:
                req = urllib.request.Request(
                    f"{self.base_url}/api/chat",
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw_body = resp.read().decode("utf-8")
                    body = json.loads(raw_body)

                elapsed_ms = (time.time() - t0) * 1000
                msg_obj = body.get("message", {})
                content = msg_obj.get("content", "").strip()
                if not content and "thinking" in msg_obj:
                    content = msg_obj.get("thinking", "").strip()

                cleaned_content = clean_llm_output(content)

                # Registrar telemetría de ejecución
                self.last_telemetry = {
                    "model":             self.model,
                    "attempt":           attempt,
                    "duration_ms":       round(elapsed_ms, 2),
                    "prompt_eval_count": body.get("prompt_eval_count", 0),
                    "eval_count":        body.get("eval_count", 0),
                    "total_duration":    body.get("total_duration", 0),
                }

                logger.debug(
                    "Ollama [%s] attempt %d success in %.1fms (eval_tokens=%d)",
                    self.model, attempt, elapsed_ms, self.last_telemetry["eval_count"]
                )
                return cleaned_content

            except (urllib.error.URLError, TimeoutError, ConnectionResetError) as e:
                last_error = e
                logger.warning(
                    "Ollama [%s] attempt %d/%d failed: %s",
                    self.model, attempt, self.max_retries, e
                )
                if attempt < self.max_retries:
                    sleep_time = self.backoff_factor * (2 ** (attempt - 1))
                    time.sleep(sleep_time)

            except (KeyError, json.JSONDecodeError) as e:
                logger.error("Ollama response parse error (%s): %s", self.model, e)
                raise ValueError(f"Respuesta inválida de Ollama: {e}") from e

        logger.error("Ollama exhausted all %d retries for %s: %s", self.max_retries, self.model, last_error)
        raise ConnectionError(
            f"Ollama no disponible en {self.base_url} tras {self.max_retries} intentos: {last_error}"
        ) from last_error

    def is_available(self) -> bool:
        """
        Verifica si Ollama está en línea y si el modelo está instalado.
        Soporta matching flexible de tags (ej: gemma4:12b-mlx vs gemma4).
        """
        models = self.get_installed_models()
        return self.model_is_installed(models or [], self.model)

    def get_installed_models(self) -> Optional[list[str]]:
        """Consulta Ollama una vez y devuelve `None` si el servidor no responde."""
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/tags",
                headers={"Accept": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            return [str(item.get("name", "")) for item in body.get("models", [])]
        except Exception:
            return None

    @staticmethod
    def model_is_installed(models: list[str], model: str) -> bool:
        target = model.strip().lower()
        target_base = target.split(":")[0]
        lowered = [name.lower() for name in models]
        return (
            any(name == target for name in lowered)
            or any(target in name or name in target for name in lowered)
            or any(name.split(":")[0] == target_base for name in lowered)
        )

    def is_server_available(self) -> bool:
        """Distingue un servidor Ollama accesible de un modelo ausente."""
        return self.get_installed_models() is not None


class MockProvider(BaseLLMProvider):
    """
    Proveedor determinista para tests automatizados cuando se configura explícitamente.
    No requiere Ollama. Las respuestas simulan comportamiento realista.
    """

    RESPONSES: dict[str, str] = {
        "ANALYST": json.dumps({
            "interpretation": "El usuario no puede conectarse a Internet desde su computadora.",
            "constraints": ["Sin acceso a hardware físico", "Solo diagnóstico de software"],
            "missing_info": ["Sistema operativo", "Tipo de conexión (WiFi/cable)", "Mensajes de error específicos"],
            "success_criteria": ["Identificar la causa raíz de la desconexión", "Proporcionar pasos de resolución verificables"],
            "category": "diagnóstico_de_red",
            "priority": "alta"
        }),
        "STRATEGIST": json.dumps({
            "plan": [
                {"id": "T1", "task": "Verificar estado de la interfaz de red", "agent": "EXECUTOR", "depends_on": []},
                {"id": "T2", "task": "Verificar resolución DNS", "agent": "EXECUTOR", "depends_on": ["T1"]},
                {"id": "T3", "task": "Verificar conectividad de gateway", "agent": "EXECUTOR", "depends_on": ["T1"]},
                {"id": "T4", "task": "Evaluar resultados y proponer solución", "agent": "EVALUATOR", "depends_on": ["T2", "T3"]},
            ],
            "strategy": "Diagnóstico en capas: físico → red → aplicación",
            "risk": "Si T1 falla, T2 y T3 no son ejecutables"
        }),
        "EXECUTOR": json.dumps({
            "action": "diagnose_network",
            "steps_executed": ["check_interface", "ping_gateway", "check_dns"],
            "results": {
                "interface": "UP",
                "gateway_ping": "SUCCESS (12ms)",
                "dns_resolution": "FAILED — timeout al resolver 8.8.8.8",
            },
            "conclusion": "La interfaz de red está activa y el gateway responde. El problema está en la resolución DNS.",
            "recommendation": "Configurar DNS alternativo: 1.1.1.1 (Cloudflare) o 8.8.8.8 (Google)"
        }),
        "EVALUATOR": json.dumps({
            "verdict": "APPROVED",
            "goal_achieved": True,
            "evidence_quality": "SUFFICIENT",
            "inconsistencies": [],
            "corrections_needed": [],
            "confidence": 0.92,
            "summary": "El diagnóstico es correcto y la solución propuesta es verificable y específica.",
            "final_answer": "Diagnóstico de conectividad completado: La interfaz de red y el enlace al gateway están operativos, pero la resolución DNS no responde. Se recomienda configurar manualmente servidores DNS alternativos (1.1.1.1 o 8.8.8.8) en la configuración de red del sistema."
        }),
        "DEFAULT": "Procesando solicitud y analizando contexto disponible."
    }

    def __init__(self, role: str = "DEFAULT"):
        self.role = role
        self.last_telemetry: dict[str, Any] = {
            "model": f"mock-{role.lower()}",
            "duration_ms": 1.0,
            "eval_count": 50,
        }

    def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        role = self.role
        if role == "DEFAULT":
            for key in self.RESPONSES:
                if key.lower() in system_prompt.lower():
                    role = key
                    break
        return self.RESPONSES.get(role, self.RESPONSES["DEFAULT"])

    def is_available(self) -> bool:
        return True


def build_provider(agent_role: str, config: Optional[dict[str, Any]] = None) -> BaseLLMProvider:
    """
    Factory que construye el proveedor configurado. Ollama no se sustituye
    silenciosamente por respuestas simuladas cuando no está disponible.
    """
    if config is None:
        from nexo.config import PROVIDER_CONFIG
        config = PROVIDER_CONFIG

    provider_cfg = config.get(agent_role)
    if provider_cfg is None:
        raise KeyError(f"No hay configuración de proveedor para el rol {agent_role}")
    ptype = str(provider_cfg.get("type", "")).lower()

    if ptype == "ollama":
        model    = provider_cfg.get("model", "gemma4:12b-mlx")
        base_url = provider_cfg.get("base_url", OLLAMA_BASE_URL)
        timeout  = provider_cfg.get("timeout", 120)
        retries  = provider_cfg.get("retries", 3)

        provider = OllamaProvider(model=model, base_url=base_url, timeout=timeout, max_retries=retries)
        if not provider.is_available():
            raise ConnectionError(
                f"Ollama o el modelo '{model}' no está disponible en {base_url} para {agent_role}. "
                "Iniciá Ollama o configurá explícitamente type='mock' solo para pruebas."
            )
        return provider

    if ptype == "mock":
        return MockProvider(role=agent_role)
    raise ValueError(f"Proveedor no soportado para {agent_role}: {ptype}")
