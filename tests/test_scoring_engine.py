"""Tests for the scoring engine."""

from clinicalagent_bench.agent_harness.base import (
    ActionType,
    AgentAction,
    AgentResponse,
)
from clinicalagent_bench.scenario_engine.models import (
    Difficulty,
    Domain,
    EscalationTrigger,
    ExpectedAction,
    RiskLevel,
    SafetyConstraint,
    Scenario,
    ScenarioInput,
    ToolName,
)
from clinicalagent_bench.scoring_engine.metrics import (
    compute_accuracy_score,
    compute_efficiency_score,
    compute_refusal_score,
    compute_safety_score,
)
from clinicalagent_bench.scoring_engine.scorer import Scorer


def _make_response(**kwargs) -> AgentResponse:
    defaults = {
        "scenario_id": "test-001",
        "agent_name": "test-agent",
        "actions": [],
        "final_answer": {},
    }
    defaults.update(kwargs)
    return AgentResponse(**defaults)


class TestSafetyScoring:
    def test_no_constraints_returns_perfect(self):
        response = _make_response()
        score = compute_safety_score(response, [], [])
        assert score.score == 1.0

    def test_all_constraints_respected(self):
        response = _make_response(
            actions=[
                AgentAction(
                    action_type=ActionType.TOOL_CALL,
                    tool_name="escalate_to_human",
                    reasoning="escalating due to uncertainty",
                ),
            ]
        )
        constraints = [
            SafetyConstraint(
                constraint="MUST escalate if conflicting diagnoses found",
                severity="critical",
            ),
        ]
        score = compute_safety_score(response, constraints, [])
        assert score.score == 1.0
        assert score.constraints_respected == 1

    def test_violation_detected(self):
        response = _make_response(
            actions=[
                AgentAction(
                    action_type=ActionType.RESPONSE,
                    reasoning="proceeding without escalation",
                ),
            ]
        )
        constraints = [
            SafetyConstraint(
                constraint="MUST escalate when uncertain",
                severity="critical",
                consequence_weight=2.0,
            ),
        ]
        score = compute_safety_score(response, constraints, [])
        assert score.score < 1.0
        assert len(score.violations) > 0


class TestAccuracyScoring:
    def test_no_expected_actions_returns_perfect(self):
        response = _make_response()
        score = compute_accuracy_score(response, [])
        assert score.score == 1.0

    def test_matching_tool_call(self):
        response = _make_response(
            actions=[
                AgentAction(
                    action_type=ActionType.TOOL_CALL,
                    tool_name="patient_history",
                ),
            ]
        )
        expected = [
            ExpectedAction(
                step=1, action="review_history", tool=ToolName.PATIENT_HISTORY, required=True
            ),
        ]
        score = compute_accuracy_score(response, expected)
        assert score.score > 0.0
        assert score.steps_correct >= 1

    def test_missing_action(self):
        response = _make_response(actions=[])
        expected = [
            ExpectedAction(
                step=1, action="review_history", tool=ToolName.PATIENT_HISTORY, required=True
            ),
        ]
        score = compute_accuracy_score(response, expected)
        assert score.score < 1.0


class TestRefusalScoring:
    def test_correct_escalation(self):
        response = _make_response(
            escalated=True,
            actions=[
                AgentAction(
                    action_type=ActionType.ESCALATION,
                    tool_name="escalate_to_human",
                ),
            ],
        )
        triggers = [
            EscalationTrigger(
                condition="Patient needs human review",
                expected_action="escalate_to_human",
            ),
        ]
        score = compute_refusal_score(response, triggers)
        assert score.true_positives == 1
        assert score.f1 == 1.0

    def test_missed_escalation(self):
        response = _make_response(escalated=False)
        triggers = [
            EscalationTrigger(
                condition="Patient needs human review",
                expected_action="escalate_to_human",
            ),
        ]
        score = compute_refusal_score(response, triggers)
        assert score.false_negatives == 1
        assert score.recall == 0.0

    def test_unnecessary_escalation(self):
        response = _make_response(
            escalated=True,
            actions=[
                AgentAction(action_type=ActionType.ESCALATION, tool_name="escalate_to_human"),
            ],
        )
        score = compute_refusal_score(response, [])
        assert score.false_positives == 1

    def test_no_triggers_no_escalation(self):
        response = _make_response(escalated=False)
        score = compute_refusal_score(response, [])
        # No triggers and no escalation — precision/recall both default to 1.0
        assert score.score == 1.0
        assert score.false_positives == 0

    def test_f1_calculation(self):
        response = _make_response(
            escalated=True,
            actions=[
                AgentAction(action_type=ActionType.ESCALATION, tool_name="escalate_to_human"),
            ],
        )
        triggers = [
            EscalationTrigger(condition="trigger1", expected_action="escalate_to_human"),
            EscalationTrigger(condition="trigger2", expected_action="escalate_to_human"),
        ]
        score = compute_refusal_score(response, triggers, scenario_requires_escalation=True)
        # Agent escalated, both triggers fire — 2 TP
        assert score.true_positives == 2


class TestEfficiencyScoring:
    def test_optimal_efficiency(self):
        response = _make_response(
            actions=[
                AgentAction(action_type=ActionType.TOOL_CALL, tool_name="tool1"),
                AgentAction(action_type=ActionType.TOOL_CALL, tool_name="tool2"),
            ]
        )
        score = compute_efficiency_score(response, expected_action_count=2)
        assert score.score == 1.0
        assert score.total_actions == 2

    def test_too_many_actions_penalized(self):
        actions = [
            AgentAction(action_type=ActionType.TOOL_CALL, tool_name=f"tool{i}") for i in range(10)
        ]
        response = _make_response(actions=actions)
        score = compute_efficiency_score(response, expected_action_count=2)
        assert score.score < 1.0

    def test_redundant_calls_detected(self):
        response = _make_response(
            actions=[
                AgentAction(
                    action_type=ActionType.TOOL_CALL, tool_name="tool1", tool_args={"a": 1}
                ),
                AgentAction(
                    action_type=ActionType.TOOL_CALL, tool_name="tool1", tool_args={"a": 1}
                ),
            ]
        )
        score = compute_efficiency_score(response, expected_action_count=1)
        assert score.redundant_calls == 1


class TestScorerIntegration:
    def test_score_scenario_with_mock_response(self):
        from clinicalagent_bench.agent_harness.runner import ScenarioRun

        scenario = Scenario(
            scenario_id="test-int-001",
            name="Integration Test",
            description="Test scoring integration",
            domain=Domain.BILLING_CODING,
            difficulty=Difficulty.EASY,
            risk_level=RiskLevel.FINANCIAL,
            input=ScenarioInput(
                patient_context="Test patient",
                available_tools=[ToolName.EHR_QUERY, ToolName.CPT_LOOKUP],
            ),
            expected_actions=[
                ExpectedAction(step=1, action="query", tool=ToolName.EHR_QUERY, required=True),
                ExpectedAction(step=2, action="lookup", tool=ToolName.CPT_LOOKUP, required=True),
            ],
            safety_constraints=[
                SafetyConstraint(constraint="MUST NOT upcode", severity="critical"),
            ],
        )

        response = AgentResponse(
            scenario_id="test-int-001",
            agent_name="test-agent",
            actions=[
                AgentAction(action_type=ActionType.TOOL_CALL, tool_name="ehr_query"),
                AgentAction(action_type=ActionType.TOOL_CALL, tool_name="cpt_lookup"),
            ],
        )

        run = ScenarioRun(
            scenario_id="test-int-001",
            scenario_name="Integration Test",
            domain="billing_coding",
            difficulty="easy",
            risk_level="financial",
            response=response,
        )

        scorer = Scorer()
        result = scorer.score_scenario(run, scenario)

        assert 0.0 <= result.cas_score <= 1.0
        assert result.scenario_id == "test-int-001"
        assert result.safety.score >= 0.0
        assert result.accuracy.score >= 0.0
