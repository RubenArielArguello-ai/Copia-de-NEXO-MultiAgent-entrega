"""
Tests de integración y resiliencia del proveedor Ollama.

Verifica:
- Limpieza de etiquetas de pensamiento (<thought>...</thought>, <think>...</think>)
- Lógica de reintentos con backoff ante caídas temporales
- Manejo de timeouts y errores de conexión
- Extracción de telemetría de ejecución (tokens, duración)
- Matching flexible de modelos y fallback automático a MockProvider
"""

import sys
import os
import json
import httpx
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    import pytest
except ImportError:
    class _RaisesContext:
        def __init__(self, exc): self.exc = exc
        def __enter__(self): return self
        def __exit__(self, et, ev, tb):
            if et is None: raise AssertionError(f"Expected {self.exc}")
            return issubclass(et, self.exc)

    class _PytestStub:
        raises = staticmethod(lambda exc: _RaisesContext(exc))
        main = staticmethod(lambda args=None: 0)
    pytest = _PytestStub()

from nexo.providers.base_provider import (
    OllamaProvider, MockProvider, build_provider, clean_llm_output
)


class TestOllamaProviderHelpers:
    """Verifica utilidades del proveedor."""

    def test_clean_llm_output_removes_thinking_tags(self):
        """Etiquetas de pensamiento de modelos reasoning deben ser eliminadas."""
        raw = "<thought>\nAnalizando el problema del usuario...\nDebería sugerir DNS.\n</thought>```json\n{\"status\": \"ok\"}\n```"
        cleaned = clean_llm_output(raw)
        assert "<thought>" not in cleaned
        assert "</thought>" not in cleaned
        assert '{"status": "ok"}' in cleaned

    def test_clean_llm_output_removes_think_tags(self):
        raw = "<think>Paso 1: analizar</think>Respuesta limpia"
        assert clean_llm_output(raw) == "Respuesta limpia"


class TestOllamaProviderLogic:
    """Verifica el comportamiento de OllamaProvider con mocks de red."""

    @patch("httpx.Client.post")
    def test_successful_generate_with_telemetry(self, mock_post):
        """Una llamada exitosa debe devolver contenido y registrar telemetría."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"content": "Respuesta correcta"},
            "prompt_eval_count": 15,
            "eval_count": 42,
            "total_duration": 150000000,
        }
        mock_post.return_value = mock_response

        provider = OllamaProvider(model="gemma4:12b-mlx", max_retries=2)
        resp = provider.generate("System prompt", "User prompt")

        assert resp == "Respuesta correcta"
        assert provider.last_telemetry["eval_count"] == 42
        assert provider.last_telemetry["prompt_eval_count"] == 15
        assert provider.last_telemetry["duration_ms"] >= 0

    @patch("httpx.Client.post")
    def test_retries_on_transient_network_error(self, mock_post):
        """Debe reintentar ante error transitorio y tener éxito en el segundo intento."""
        mock_ctx1 = MagicMock()
        failure = httpx.ConnectError("Connection reset", request=httpx.Request("POST", "http://ollama/api/chat"))
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "message": {"content": "Éxito tras reintento"},
            "eval_count": 10,
        }

        mock_post.side_effect = [failure, mock_resp]

        provider = OllamaProvider(model="gemma4:12b-mlx", max_retries=2, backoff_factor=0.01)
        resp = provider.generate("System", "User")
        assert resp == "Éxito tras reintento"
        assert provider.last_telemetry["attempt"] == 2

    @patch("httpx.Client.post")
    def test_exhausted_retries_raises_connection_error(self, mock_post):
        """Si todos los reintentos fallan, debe lanzar ConnectionError."""
        mock_post.side_effect = httpx.ConnectError("Service unreachable", request=httpx.Request("POST", "http://ollama/api/chat"))

        provider = OllamaProvider(model="gemma4:12b-mlx", max_retries=2, backoff_factor=0.01)
        with pytest.raises(ConnectionError):
            provider.generate("System", "User")

    @patch("httpx.Client.get")
    def test_is_available_fuzzy_matching(self, mock_get):
        """Verifica matching de nombres con y sin tags."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "gemma4:12b-mlx"},
                {"name": "qwen2.5-coder:7b"},
            ]
        }
        mock_get.return_value = mock_response

        # Coincidencia exacta
        p1 = OllamaProvider(model="gemma4:12b-mlx")
        assert p1.is_available() is True

        # Coincidencia por base
        p2 = OllamaProvider(model="qwen2.5-coder")
        assert p2.is_available() is True

        # Modelo inexistente
        p3 = OllamaProvider(model="modelo-fantasma-no-instalado:99b")
        assert p3.is_available() is False


class TestProviderFactory:
    """Verifica el factory build_provider sin ocultar fallos del proveedor real."""

    def test_build_provider_returns_mock_when_specified(self):
        cfg = {"ANALYST": {"type": "mock"}}
        p = build_provider("ANALYST", cfg)
        assert isinstance(p, MockProvider)

    @patch.object(OllamaProvider, "is_available", return_value=False)
    def test_build_provider_fails_when_configured_ollama_is_unavailable(self, mock_avail):
        cfg = {"EXECUTOR": {"type": "ollama", "model": "qwen2.5-coder:7b"}}
        with pytest.raises(ConnectionError, match="no está disponible"):
            build_provider("EXECUTOR", cfg)

    def test_providers_share_keepalive_client_for_same_endpoint(self, monkeypatch):
        key = ("http://reuse-test.invalid:11434", 120)
        OllamaProvider._clients.pop(key, None)
        client = MagicMock()
        factory = MagicMock(return_value=client)
        monkeypatch.setattr("nexo.providers.base_provider.httpx.Client", factory)
        first = OllamaProvider("one", key[0], timeout=key[1])
        second = OllamaProvider("two", key[0], timeout=key[1])
        assert first._client is second._client is client
        factory.assert_called_once()
        OllamaProvider._clients.pop(key, None)
