import socket
from unittest.mock import MagicMock

from nexo.skills import SkillRegistry
from nexo.tools.analysis_tools import (
    CodeEngineeringTool, HTTPHealthCheckTool, LogAnalysisTool, ReportGenerationTool,
)
from nexo.agents.evaluator import EvaluatorAgent
from nexo.providers.base_provider import MockProvider
from nexo.schemas.message import AgentID, NexoMessage, TaskPhase, MessageStatus


def test_log_analysis_is_bounded_and_redacts_secrets(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.log").write_text("ERROR password=secret-value\nWARN cache slow\n", encoding="utf-8")
    result = LogAnalysisTool().safe_execute({"path": "app.log"})
    assert result["success"]
    assert result["output"]["pattern_counts"]["error"] == 1
    assert "secret-value" not in str(result["output"])


def test_code_engineering_reports_syntax_without_executing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "bad.py").write_text("def broken(:\n", encoding="utf-8")
    result = CodeEngineeringTool().safe_execute({"path": "bad.py"})
    assert result["success"]
    assert result["output"]["syntax_valid"] is False
    assert result["output"]["executed"] is False


def test_http_health_check_blocks_private_networks(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))])
    result = HTTPHealthCheckTool().safe_execute({"url": "http://example.test/health"})
    assert result["success"] is False
    assert "SSRF" in result["error"]


def test_http_health_check_reports_response_metadata(monkeypatch):
    class Response:
        status = 200
        def read(self, limit): return b"ok"
    class Connection:
        sock = None
        def __init__(self, *args, **kwargs): pass
        def request(self, *args, **kwargs): pass
        def getresponse(self): return Response()
        def close(self): pass
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])
    monkeypatch.setattr(socket, "create_connection", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("nexo.tools.analysis_tools.http.client.HTTPConnection", Connection)
    result = HTTPHealthCheckTool().safe_execute({"url": "http://example.test/health?token=secret"})
    assert result["success"]
    assert result["output"]["status_code"] == 200
    assert result["output"]["healthy"] is True
    assert "secret" not in result["output"]["url"]


def test_report_only_uses_observed_results():
    result = ReportGenerationTool().safe_execute({"request": "diagnóstico", "prior_results": [
        {"task_id": "T1", "result": {"tool_used": "system_diagnostic", "tool_success": True,
         "raw_results": {"cpu_count": 8}}}
    ]})
    assert result["success"]
    assert result["output"]["evidence"][0]["observed"] == {"cpu_count": 8}


def test_evaluator_approves_only_complete_registered_skill_evidence():
    request = "Revisa recursos del sistema y conectividad, y genera un informe"
    results = []
    for tool in ("system_diagnostic", "network_diagnostic"):
        results.append({"task_id": tool, "result": {"tool_used": tool, "tool_success": True,
                        "can_complete": True, "raw_results": {"observed": True}}})
    report = ReportGenerationTool().safe_execute({"request": request, "prior_results": results})["output"]
    results.append({"task_id": "report", "result": {"tool_used": "report_generation", "tool_success": True,
                    "can_complete": True, "raw_results": report}})
    message = NexoMessage(from_agent=AgentID.ORCHESTRATOR, to_agent=AgentID.EVALUATOR,
        task_id="unit", goal=request, phase=TaskPhase.EVALUATION,
        payload={"execution_results": results, "analysis": {}},
        context={"original_request": request}, status=MessageStatus.PENDING)
    result = EvaluatorAgent(MockProvider("EVALUATOR"), None).process(message)
    assert result.payload["evaluation"]["verdict"] == "APPROVED"
    assert result.payload["evaluation"]["evaluation_method"] == "deterministic_skill_evidence_gate"


def test_evaluator_rejects_conflicting_literal_file_evidence():
    request = 'Crea el archivo resultado.txt con el contenido exacto "correcto"'
    results = [
        {"task_id": "write", "result": {"tool_used": "file_write", "tool_success": True,
         "can_complete": True, "raw_results": {"content": "incorrecto"}}}
    ]
    message = NexoMessage(from_agent=AgentID.ORCHESTRATOR, to_agent=AgentID.EVALUATOR,
        task_id="unit-file", goal=request, phase=TaskPhase.EVALUATION,
        payload={"execution_results": results, "analysis": {}},
        context={"original_request": request}, status=MessageStatus.PENDING)
    evaluated = EvaluatorAgent(MockProvider("EVALUATOR"), None).process(message)
    assert evaluated.payload["evaluation"]["verdict"] == "REJECTED"


def test_registry_selects_composite_mission_skills():
    skills = SkillRegistry().select_all("Diagnostica recursos del sistema y conectividad; genera un informe")
    assert {skill.tool_name for skill in skills} >= {"system_diagnostic", "network_diagnostic", "report_generation"}
    registry = SkillRegistry()
    assert registry.select("report_generation: inspect sistema y red").name == "report_generation"
