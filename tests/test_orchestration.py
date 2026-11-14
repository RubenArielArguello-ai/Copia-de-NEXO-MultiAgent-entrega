import unittest
from unittest.mock import patch
from nexo.core.orchestrator import Orchestrator
from nexo.core.state_manager import StateManager
from nexo.providers.base_provider import MockProvider

class TestOrchestration(unittest.TestCase):
    def setUp(self):
        self.state_manager = StateManager()
        self.orchestrator = Orchestrator(self.state_manager)
        self.network_patch = patch(
            "nexo.tools.diagnostic_tool.NetworkDiagnosticTool.execute",
            return_value={"tool": "network_diagnostic", "output": {"status": "mocked"}, "success": True},
        )
        self.network_patch.start()

    def tearDown(self):
        self.network_patch.stop()

    def test_orchestration_flow(self):
        with patch("nexo.core.orchestrator.build_provider", side_effect=lambda role, cfg: MockProvider(role)):
            session = self.state_manager.create_session("Test Mission: diagnosticar la conexión a Internet")
            result = self.orchestrator.run(session.session_id)

        self.assertIn(result["status"], ("COMPLETED", "FAILED"))
        recipients = {message["to_agent"] for message in result["messages"]}
        self.assertTrue({"ANALYST", "STRATEGIST", "EXECUTOR", "EVALUATOR"}.issubset(recipients))

if __name__ == '__main__':
    unittest.main()
