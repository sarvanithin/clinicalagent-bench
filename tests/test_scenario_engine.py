"""Tests for the scenario engine: models, loader, and registry."""

from pathlib import Path

import pytest

from clinicalagent_bench.scenario_engine.loader import ScenarioLoader
from clinicalagent_bench.scenario_engine.models import (
    Difficulty,
    Domain,
    ExpectedAction,
    RiskLevel,
    SafetyConstraint,
    Scenario,
    ScenarioInput,
    ScoringConfig,
    ToolName,
)
from clinicalagent_bench.scenario_engine.registry import ScenarioRegistry

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"


class TestScenarioModels:
    def test_scenario_input_creation(self):
        inp = ScenarioInput(
            patient_context="65yo male with diabetes",
            available_tools=[ToolName.EHR_QUERY, ToolName.CPT_LOOKUP],
        )
        assert inp.patient_context == "65yo male with diabetes"
        assert len(inp.available_tools) == 2

    def test_expected_action(self):
        action = ExpectedAction(
            step=1,
            action="query_patient",
            tool=ToolName.PATIENT_HISTORY,
            required=True,
        )
        assert action.step == 1
        assert action.required is True
        assert action.tool == ToolName.PATIENT_HISTORY

    def test_safety_constraint(self):
        constraint = SafetyConstraint(
            constraint="MUST NOT upcode",
            severity="critical",
            consequence_weight=2.0,
        )
        assert constraint.severity == "critical"
        assert constraint.consequence_weight == 2.0

    def test_scoring_config_defaults(self):
        config = ScoringConfig()
        assert config.accuracy_weight == 0.3
        assert config.safety_weight == 0.4
        total = (
            config.accuracy_weight
            + config.safety_weight
            + config.completeness_weight
            + config.efficiency_weight
        )
        assert total == pytest.approx(1.0)

    def test_full_scenario_creation(self):
        scenario = Scenario(
            scenario_id="test-001",
            name="Test Scenario",
            description="A test scenario",
            domain=Domain.BILLING_CODING,
            difficulty=Difficulty.MEDIUM,
            risk_level=RiskLevel.FINANCIAL,
            input=ScenarioInput(
                patient_context="Test patient",
                available_tools=[ToolName.EHR_QUERY],
            ),
            expected_actions=[ExpectedAction(step=1, action="test_action", required=True)],
        )
        assert scenario.scenario_id == "test-001"
        assert scenario.domain == Domain.BILLING_CODING


class TestScenarioLoader:
    def test_load_billing_scenarios(self):
        loader = ScenarioLoader(SCENARIOS_DIR)
        scenarios = loader.load_directory("billing")
        assert len(scenarios) >= 10
        for s in scenarios:
            assert s.domain == Domain.BILLING_CODING

    def test_load_triage_scenarios(self):
        loader = ScenarioLoader(SCENARIOS_DIR)
        scenarios = loader.load_directory("triage")
        assert len(scenarios) >= 10
        for s in scenarios:
            assert s.domain == Domain.TRIAGE_SCHEDULING

    def test_load_all_scenarios(self):
        loader = ScenarioLoader(SCENARIOS_DIR)
        all_scenarios = loader.load_all()
        assert len(all_scenarios) > 0
        total = sum(len(v) for v in all_scenarios.values())
        assert total >= 35  # We have at least 35 scenarios

    def test_load_nonexistent_directory(self):
        loader = ScenarioLoader(Path("/nonexistent"))
        result = loader.load_all()
        assert result == {}

    def test_load_specific_file(self):
        billing_file = SCENARIOS_DIR / "billing" / "billing-001.yaml"
        if billing_file.exists():
            loader = ScenarioLoader(SCENARIOS_DIR)
            scenario = loader.load_file(billing_file)
            assert scenario.scenario_id == "billing-001"
            assert scenario.domain == Domain.BILLING_CODING


class TestScenarioRegistry:
    def _make_registry(self) -> ScenarioRegistry:
        loader = ScenarioLoader(SCENARIOS_DIR)
        registry = ScenarioRegistry()
        all_scenarios = loader.load_all()
        for group in all_scenarios.values():
            registry.register_many(group)
        return registry

    def test_registry_count(self):
        registry = self._make_registry()
        assert registry.count >= 35

    def test_filter_by_domain(self):
        registry = self._make_registry()
        billing = registry.filter(domain=Domain.BILLING_CODING)
        assert len(billing) >= 10
        for s in billing:
            assert s.domain == Domain.BILLING_CODING

    def test_filter_by_difficulty(self):
        registry = self._make_registry()
        hard = registry.filter(difficulty=Difficulty.HARD)
        assert len(hard) > 0
        for s in hard:
            assert s.difficulty == Difficulty.HARD

    def test_filter_combined(self):
        registry = self._make_registry()
        result = registry.filter(
            domain=Domain.TRIAGE_SCHEDULING,
            risk_level=RiskLevel.PATIENT_SAFETY,
        )
        for s in result:
            assert s.domain == Domain.TRIAGE_SCHEDULING
            assert s.risk_level == RiskLevel.PATIENT_SAFETY

    def test_get_by_id(self):
        registry = self._make_registry()
        scenario = registry.get("billing-001")
        assert scenario is not None
        assert scenario.name == "Annual Wellness Visit with Wound Care"

    def test_get_nonexistent(self):
        registry = self._make_registry()
        assert registry.get("nonexistent-999") is None

    def test_domains_summary(self):
        registry = self._make_registry()
        summary = registry.domains_summary()
        assert "billing_coding" in summary
        assert summary["billing_coding"] >= 10

    def test_list_ids(self):
        registry = self._make_registry()
        ids = registry.list_ids()
        assert len(ids) >= 35
        assert "billing-001" in ids


class TestScenarioYAMLValidity:
    """Validate all YAML scenarios parse correctly."""

    def test_all_scenarios_have_required_fields(self):
        loader = ScenarioLoader(SCENARIOS_DIR)
        all_scenarios = loader.load_all()
        for domain, scenarios in all_scenarios.items():
            for s in scenarios:
                assert s.scenario_id, f"Missing scenario_id in {domain}"
                assert s.name, f"Missing name for {s.scenario_id}"
                assert s.input.patient_context, f"Missing patient_context for {s.scenario_id}"
                assert len(s.expected_actions) > 0, f"No expected actions for {s.scenario_id}"
                assert len(s.input.available_tools) > 0, f"No tools for {s.scenario_id}"

    def test_all_scenarios_have_safety_or_escalation(self):
        """Every scenario should have either safety constraints or escalation triggers (or both)."""
        loader = ScenarioLoader(SCENARIOS_DIR)
        all_scenarios = loader.load_all()
        for domain, scenarios in all_scenarios.items():
            for s in scenarios:
                has_safety = len(s.safety_constraints) > 0
                has_escalation = len(s.escalation_triggers) > 0
                assert has_safety or has_escalation, (
                    f"Scenario {s.scenario_id} has no safety constraints or escalation triggers"
                )

    def test_scoring_weights_reasonable(self):
        loader = ScenarioLoader(SCENARIOS_DIR)
        all_scenarios = loader.load_all()
        for domain, scenarios in all_scenarios.items():
            for s in scenarios:
                total = (
                    s.scoring.accuracy_weight
                    + s.scoring.safety_weight
                    + s.scoring.completeness_weight
                    + s.scoring.efficiency_weight
                )
                assert 0.9 <= total <= 1.1, (
                    f"Scoring weights for {s.scenario_id} sum to {total}, expected ~1.0"
                )
