from pathlib import Path

from nexo.skills import SkillRegistry
from nexo.tools.basic_tools import ejecutar_codigo_python, leer_archivo
from fastapi.testclient import TestClient
from api.main import app


def test_skill_registry_selects_only_matching_executor_capability():
    registry = SkillRegistry()
    skill = registry.select("Revisar CPU y recursos del sistema")
    assert skill and skill.name == "system_diagnostics"
    assert registry.select("Analizar registros de errores").name == "log_analysis"
    assert registry.authorize(skill.name, "EXECUTOR", "read")
    assert not registry.authorize(skill.name, "ANALYST", "read")


def test_legacy_file_tool_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = leer_archivo.invoke({"ruta": "../../etc/passwd"})
    assert "Error" in result


def test_legacy_python_tool_only_evaluates_arithmetic():
    assert "Resultado: 4" in ejecutar_codigo_python.invoke({"codigo": "2 + 2"})
    blocked = ejecutar_codigo_python.invoke({"codigo": "__import__('os').system('id')"})
    assert "rechazada" in blocked.lower()


def test_api_bearer_token_is_enforced(monkeypatch):
    monkeypatch.setenv("NEXO_API_TOKEN", "test-only-token")
    monkeypatch.delenv("NEXO_ENV", raising=False)
    client = TestClient(app)
    assert client.get("/tools").status_code == 401
    response = client.get("/tools", headers={"Authorization": "Bearer test-only-token"})
    assert response.status_code == 200


def test_agent_status_exposes_real_specialist_roles(monkeypatch):
    monkeypatch.delenv("NEXO_API_TOKEN", raising=False)
    client = TestClient(app)
    response = client.get("/agents/status")
    assert response.status_code == 200
    roles = response.json()["agents"]
    assert {"ORCHESTRATOR", "ANALYST", "RESEARCHER", "STRATEGIST", "EXECUTOR",
            "QA", "SECURITY", "EVALUATOR"}.issubset(roles)
    assert roles["QA"]["provider"] == "internal"
    assert roles["SECURITY"]["provider"] == "internal"
