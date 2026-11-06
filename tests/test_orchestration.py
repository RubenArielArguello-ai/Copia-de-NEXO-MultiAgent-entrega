import unittest
from nexo.core.orquestador import Orquestrator
from nexo.agents.analyst_agent import AnalystAgent
from nexo.agents.strategist_agent import StrategistAgent
from nexo.agents.executor_agent import ExecutorAgent
from nexo.agents.evaluator_agent import EvaluatorAgent
from nexo.core.message_bus import MessageBus

class TestOrchestration(unittest.TestCase):
    def setUp(self):
        self.bus = MessageBus("test_session")
        self.orquestrator = Orquestrador(self.bus)
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
