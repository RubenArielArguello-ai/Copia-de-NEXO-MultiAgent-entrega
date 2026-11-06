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
import urllib.error
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

    @patch("urllib.request.urlopen")
    def test_successful_generate_with_telemetry(self, mock_urlopen):
        """Una llamada exitosa debe devolver contenido y registrar telemetría."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "message": {"content": "Respuesta correcta"},
            "prompt_eval_count": 15,
            "eval_count": 42,
            "total_duration": 150000000,
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        provider = OllamaProvider(model="gemma4:12b-mlx", max_retries=2)
        resp = provider.generate("System prompt", "User prompt")

        assert resp == "Respuesta correcta"
        assert provider.last_telemetry["eval_count"] == 42
        assert provider.last_telemetry["prompt_eval_count"] == 15
        assert provider.last_telemetry["duration_ms"] >= 0

    @patch("urllib.request.urlopen")
    def test_retries_on_transient_network_error(self, mock_urlopen):
        """Debe reintentar ante error transitorio y tener éxito en el segundo intento."""
        mock_ctx1 = MagicMock()
        mock_ctx1.__enter__.side_effect = urllib.error.URLError("Connection reset")

        mock_ctx2 = MagicMock()
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "message": {"content": "Éxito tras reintento"},
            "eval_count": 10,
        }).encode("utf-8")
        mock_ctx2.__enter__.return_value = mock_resp

        mock_urlopen.side_effect = [mock_ctx1, mock_ctx2]

        provider = OllamaProvider(model="gemma4:12b-mlx", max_retries=2, backoff_factor=0.01)
        resp = provider.generate("System", "User")
        assert resp == "Éxito tras reintento"
        assert provider.last_telemetry["attempt"] == 2

    @patch("urllib.request.urlopen")
    def test_exhausted_retries_raises_connection_error(self, mock_urlopen):
        """Si todos los reintentos fallan, debe lanzar ConnectionError."""
        mock_urlopen.side_effect = urllib.error.URLError("Service unreachable")

        provider = OllamaProvider(model="gemma4:12b-mlx", max_retries=2, backoff_factor=0.01)
        with pytest.raises(ConnectionError):
            provider.generate("System", "User")

    @patch("urllib.request.urlopen")
    def test_is_available_fuzzy_matching(self, mock_urlopen):
        """Verifica matching de nombres con y sin tags."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "models": [
                {"name": "gemma4:12b-mlx"},
                {"name": "qwen2.5-coder:7b"},
            ]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

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
    """Verifica el factory build_provider y su fallback."""

    def test_build_provider_returns_mock_when_specified(self):
        cfg = {"ANALYST": {"type": "mock"}}
        p = build_provider("ANALYST", cfg)
        assert isinstance(p, MockProvider)

    @patch.object(OllamaProvider, "is_available", return_value=False)
    def test_build_provider_falls_back_to_mock_when_ollama_unavailable(self, mock_avail):
        cfg = {"EXECUTOR": {"type": "ollama", "model": "qwen2.5-coder:7b"}}
        p = build_provider("EXECUTOR", cfg)
        # Como is_available devuelve False, debe caer a MockProvider
        assert isinstance(p, MockProvider)
        assert p.role == "EXECUTOR"
