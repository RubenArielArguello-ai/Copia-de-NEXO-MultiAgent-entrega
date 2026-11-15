from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_exposes_all_specialists_and_harness_panel():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    for role in ("ANALYST", "RESEARCHER", "STRATEGIST", "EXECUTOR", "QA", "SECURITY", "EVALUATOR"):
        assert f'data-agent="{role}"' in html
        assert f'data-flow="{role}"' in html
    assert 'id="harness-events"' in html
    assert 'renderHarness(session.agent_results?.harness)' in script
    assert "harness.llm_call_budget" in script


def test_dashboard_reads_observed_backend_endpoints():
    script = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    for endpoint in ("/sessions/", "/agents/status", "/dashboard/metrics", "/dashboard/logs", "/skills", "/tools", "/models"):
        assert endpoint in script
