"""Tests for the agent harness."""

import asyncio

from clinicalagent_bench.agent_harness.adapters import MockAgent
from clinicalagent_bench.agent_harness.base import ActionType, AgentAction, AgentResponse
from clinicalagent_bench.agent_harness.runner import BenchmarkRunner, RunConfig
from clinicalagent_bench.scenario_engine.models import (
    Difficulty,
    Domain,
    ExpectedAction,
    RiskLevel,
    Scenario,
    ScenarioInput,
    ToolName,
)


def _make_scenario(scenario_id: str = "test-001") -> Scenario:
    return Scenario(
        scenario_id=scenario_id,
        name="Test Scenario",
        description="A test",
        domain=Domain.BILLING_CODING,
        difficulty=Difficulty.EASY,
        risk_level=RiskLevel.OPERATIONAL,
        input=ScenarioInput(
            patient_context="Test patient context",
            available_tools=[ToolName.EHR_QUERY, ToolName.CPT_LOOKUP],
        ),
        expected_actions=[
            ExpectedAction(step=1, action="test", required=True),
        ],
    )


class TestMockAgent:
    def test_mock_agent_default_response(self):
        agent = MockAgent(agent_name="test-mock")
        assert agent.name == "test-mock"

        response = asyncio.get_event_loop().run_until_complete(
            agent.run_scenario(
                patient_context="test",
                available_tools=["ehr_query"],
                tool_descriptions={"ehr_query": "Query EHR"},
                additional_context={"scenario_id": "test-001"},
            )
        )
        assert response.agent_name == "test-mock"
        assert len(response.actions) > 0

    def test_mock_agent_custom_response(self):
        agent = MockAgent()
        custom = AgentResponse(
            scenario_id="custom-001",
            agent_name="mock-agent",
            actions=[
                AgentAction(
                    action_type=ActionType.TOOL_CALL,
                    tool_name="ehr_query",
                    reasoning="custom action",
                ),
            ],
            final_answer={"result": "custom"},
        )
        agent.set_response("custom-001", custom)

        response = asyncio.get_event_loop().run_until_complete(
            agent.run_scenario(
                patient_context="test",
                available_tools=[],
                tool_descriptions={},
                additional_context={"scenario_id": "custom-001"},
            )
        )
        assert response.final_answer == {"result": "custom"}


class TestBenchmarkRunner:
    def test_run_single_scenario(self):
        agent = MockAgent()
        scenario = _make_scenario()
        runner = BenchmarkRunner(RunConfig(timeout_seconds=10))

        run = asyncio.get_event_loop().run_until_complete(runner.run_scenario(agent, scenario))
        assert run.scenario_id == "test-001"
        assert run.timed_out is False
        assert run.response.agent_name == "mock-agent"

    def test_run_benchmark_multiple_scenarios(self):
        agent = MockAgent()
        scenarios = [_make_scenario(f"test-{i:03d}") for i in range(5)]
        runner = BenchmarkRunner(RunConfig(timeout_seconds=10))

        result = asyncio.get_event_loop().run_until_complete(runner.run_benchmark(agent, scenarios))
        assert result.total_scenarios == 5
        assert len(result.scenario_runs) == 5
        assert result.agent_name == "mock-agent"

    def test_runner_timeout(self):
        """Test that very short timeout triggers timeout handling."""

        class SlowAgent(MockAgent):
            async def run_scenario(self, **kwargs):
                await asyncio.sleep(10)
                return await super().run_scenario(**kwargs)

        agent = SlowAgent()
        scenario = _make_scenario()
        runner = BenchmarkRunner(RunConfig(timeout_seconds=0.1))

        run = asyncio.get_event_loop().run_until_complete(runner.run_scenario(agent, scenario))
        assert run.timed_out is True
        assert run.response.error == "Scenario timed out"


class TestAgentResponse:
    def test_response_serialization(self):
        response = AgentResponse(
            scenario_id="test-001",
            agent_name="test",
            actions=[
                AgentAction(
                    action_type=ActionType.TOOL_CALL,
                    tool_name="ehr_query",
                    tool_args={"patient_id": "P001"},
                ),
            ],
            final_answer={"code": "99213"},
            total_tokens=150,
            total_time_ms=1234.5,
        )
        data = response.model_dump()
        assert data["scenario_id"] == "test-001"
        assert data["total_tokens"] == 150

        # Round-trip
        restored = AgentResponse.model_validate(data)
        assert restored.scenario_id == response.scenario_id
