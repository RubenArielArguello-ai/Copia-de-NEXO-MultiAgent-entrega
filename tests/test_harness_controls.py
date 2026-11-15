import time

from nexo.core.harness import HarnessBlocked, MissionHarness
from nexo.core.basic_tools import ejecutar_codigo_python, leer_archivo
from nexo.tools.base_tool import BaseTool


def test_harness_enforces_executor_role_task_budget_and_terminal_state():
    harness = MissionHarness("test", timeout_seconds=5, max_tasks=1)
    harness.begin_task("T1", "EXECUTOR", "system_diagnostic")
    harness.finish_task("T1", "EXECUTOR", "system_diagnostic", True, 12)
    try:
        harness.begin_task("T2", "EXECUTOR", "network_diagnostic")
    except HarnessBlocked:
        pass
    else:
        raise AssertionError("task budget should block additional work")
    snapshot = harness.snapshot()
    assert snapshot["tasks_completed"] == 1
    assert snapshot["blocked_operations"] == 1
    assert snapshot["state"] == "task_budget_exceeded"


def test_harness_observes_emergency_stop(monkeypatch):
    harness = MissionHarness("stop-test", timeout_seconds=5)
    monkeypatch.setenv("NEXO_EMERGENCY_STOP", "true")
    try:
        harness.check_active()
    except HarnessBlocked:
        pass
    else:
        raise AssertionError("emergency stop should block a mission")
    assert harness.snapshot()["blocked_operations"] == 1


def test_harness_deadline_blocks_next_task():
    harness = MissionHarness("deadline-test", timeout_seconds=1)
    harness.deadline = time.monotonic() - 1
    try:
        harness.check_active()
    except HarnessBlocked:
        pass
    else:
        raise AssertionError("expired deadline should block a mission")


def test_harness_enforces_llm_call_budget():
    harness = MissionHarness("llm-budget", max_llm_calls=1)
    harness.begin_llm_call("ANALYST", "local-model")
    harness.finish_llm_call("ANALYST", "local-model", 3, telemetry={"eval_count": 2})
    try:
        harness.begin_llm_call("STRATEGIST", "local-model")
    except HarnessBlocked:
        pass
    else:
        raise AssertionError("LLM call budget should block additional inference")
    assert harness.snapshot()["llm_calls"] == 1
    assert harness.snapshot()["state"] == "llm_budget_exceeded"


def test_timed_out_tool_returns_without_waiting_for_daemon_worker():
    class SlowTool(BaseTool):
        timeout_seconds = 0.02
        @property
        def name(self): return "slow"
        @property
        def description(self): return "slow test"
        def execute(self, context):
            time.sleep(0.15)
            return {"output": {"done": True}}

    started = time.monotonic()
    result = SlowTool().safe_execute({})
    assert result["timed_out"] is True
    assert time.monotonic() - started < 0.12


def test_legacy_tools_keep_safe_path_and_python_restrictions(tmp_path):
    outside = tmp_path.parent / "outside-nexo.txt"
    read = leer_archivo.invoke({"ruta": str(outside)})
    code = ejecutar_codigo_python.invoke({"codigo": "__import__('os').system('true')"})
    assert "Error" in read
    assert "Operación rechazada" in code
    assert not outside.exists()
