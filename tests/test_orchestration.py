import unittest
from nexo.core.orchestrator import Orchestrator
from nexo.agents.analyst import AnalystAgent
from nexo.agents.strategist import StrategistAgent
from nexo.agents.executor import ExecutorAgent
from nexo.agents.evaluator import EvaluatorAgent
from nexo.core.message_bus import MessageBus

class TestOrchestration(unittest.TestCase):
    def setUp(self):
        self.bus = MessageBus("test_session")
        self.orquestrator = Orchestrator(self.bus)
        self.analyst = AnalystAgent(None, self.bus)
        self.strategist = StrategistAgent(None, self.bus)
        self.executor = ExecutorAgent(None, self.bus)
        self.evaluator = EvaluatorAgent(None, self.bus)

    def test_orchestration_flow(self):
        # Start a mission
        self.orquestrator.start_mission("Test Mission")

        # Check if the mission is distributed to agents
        messages = self.bus.get_session_messages()
        self.assertIn(AgentID.ANALYST.value, [msg.to_agent for msg in messages])
        self.assertIn(AgentID.STRATEGIST.value, [msg.to_agent for msg in messages])
        self.assertIn(AgentID.EXECUTOR.value, [msg.to_agent for msg in messages])
        self.assertIn(AgentID.EVALUATOR.value, [msg.to_agent for msg in messages])

if __name__ == '__main__':
    unittest.main()
