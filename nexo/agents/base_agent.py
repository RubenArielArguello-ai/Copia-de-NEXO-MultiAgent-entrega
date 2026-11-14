"""
NEXO — Clase base para todos los agentes.

Define la interfaz común: recibir mensajes, procesar con LLM,
parseo resiliente de JSON, telemetría y publicación de respuestas.
"""

from __future__ import annotations
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Optional

from nexo.schemas.message import NexoMessage, AgentID, MessageStatus
from nexo.core.message_bus import MessageBus
from nexo.providers.base_provider import BaseLLMProvider, clean_llm_output

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Agente base de NEXO.

    Cada agente tiene:
    - Una identidad (AgentID)
    - Un proveedor LLM (intercambiable)
    - Un system prompt que define su skill
    - Acceso al bus de mensajes para comunicarse
    """

    agent_id: AgentID

    def __init__(self, provider: BaseLLMProvider, bus: MessageBus):
        self.provider = provider
        self.bus      = bus
        self._log     = logging.getLogger(f"nexo.agent.{self.agent_id.value.lower()}")

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Prompt de sistema que define el skill y comportamiento del agente."""

    @abstractmethod
    def process(self, msg: NexoMessage) -> NexoMessage:
        """
        Procesa un mensaje entrante y devuelve la respuesta.
        Cada agente implementa su lógica de razonamiento aquí.
        """

    def call_llm(self, user_prompt: str, **kwargs) -> str:
        """Llama al proveedor LLM con el system prompt del agente."""
        self._log.info("Calling LLM for %s", self.agent_id.value)
        return self.provider.generate(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            **kwargs,
        )

    def call_llm_json(self, user_prompt: str, max_attempts: int = 2) -> dict[str, Any]:
        """Solicita JSON y reintenta una vez con instrucciones de reparación si el parseo falla."""
        raw = self.call_llm(user_prompt, format="json", max_tokens=1024)
        parsed = self.parse_json_response(raw)
        attempt = 1
        while parsed.get("parse_error") and attempt < max_attempts:
            attempt += 1
            repair_prompt = (
                f"{user_prompt}\n\nTu respuesta anterior no era JSON válido. "
                "Devuelve únicamente un objeto JSON válido con los campos solicitados. "
                f"Respuesta anterior (referencia): {raw[:1500]}"
            )
            raw = self.call_llm(repair_prompt, format="json", max_tokens=1024)
            parsed = self.parse_json_response(raw)
        return parsed

    def parse_json_response(self, raw: str) -> dict[str, Any]:
        """
        Intenta parsear la respuesta del LLM como JSON de manera ultra-resiliente.
        1. Limpia bloques de pensamiento (<thought>...</thought>).
        2. Extrae bloques de código ```json ... ``` o ``` ... ```.
        3. Si falla, extrae la región entre la primera '{' y la última '}'.
        4. Corrige comas finales antes de llaves o corchetes.
        5. Si aún falla, envuelve la respuesta con 'parse_error': True.
        """
        text = clean_llm_output(raw)

        # 1. Extraer bloque markdown si existe
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text, flags=re.IGNORECASE)
        candidate = match.group(1).strip() if match else text

        # 2. Intento directo
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        # 3. Extraer desde el primer '{' hasta el último '}'
        start = candidate.find("{")
        end   = candidate.rfind("}")
        if start != -1 and end != -1 and end > start:
            slice_text = candidate[start:end+1]
            try:
                return json.loads(slice_text)
            except json.JSONDecodeError:
                # 4. Limpieza de comas colgantes (trailing commas) comunes en LLMs
                fixed = re.sub(r',\s*([\]\}])', r'\1', slice_text)
                try:
                    return json.loads(fixed)
                except json.JSONDecodeError:
                    pass

        self._log.warning("LLM response for %s is not valid JSON, wrapping as text", self.agent_id.value)
        return {
            "raw_response": raw,
            "cleaned_text": text,
            "parse_error":  True
        }

    def publish(self, msg: NexoMessage) -> None:
        """Publica un mensaje en el bus de comunicación."""
        self.bus.publish(msg)
        self._log.info(
            "Published: %s → %s [%s]",
            msg.from_agent.value,
            msg.to_agent.value,
            msg.status.value
        )

    def run(self) -> Optional[NexoMessage]:
        """
        Ciclo principal: consume el próximo mensaje del bus
        destinado a este agente y lo procesa.
        """
        msg = self.bus.consume(self.agent_id)
        if msg is None:
            return None
        self._log.info("Received message from %s (Phase: %s)", msg.from_agent.value, msg.phase.value)
        response = self.process(msg)
        self.publish(response)
        return response
