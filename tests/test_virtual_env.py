"""Tests for the virtual clinical environment."""

from clinicalagent_bench.virtual_env.ehr import MockEHR
from clinicalagent_bench.virtual_env.patient import PatientGenerator
from clinicalagent_bench.virtual_env.payer_rules import PayerRuleEngine
from clinicalagent_bench.virtual_env.tools import ToolRegistry


class TestPatientGenerator:
    def test_generate_single_patient(self):
        gen = PatientGenerator(seed=42)
        patient = gen.generate(patient_id="P00001")
        assert patient.patient_id == "P00001"
        assert 18 <= patient.age <= 90
        assert patient.insurance is not None
        assert len(patient.diagnoses) > 0

    def test_generate_cohort(self):
        gen = PatientGenerator(seed=42)
        cohort = gen.generate_cohort(10)
        assert len(cohort) == 10
        ids = {p.patient_id for p in cohort}
        assert len(ids) == 10  # All unique

    def test_generate_with_overrides(self):
        gen = PatientGenerator(seed=42)
        patient = gen.generate(age=75, sex="Female")
        assert patient.age == 75
        assert patient.sex == "Female"

    def test_deterministic_with_seed(self):
        gen1 = PatientGenerator(seed=123)
        gen2 = PatientGenerator(seed=123)
        p1 = gen1.generate(patient_id="P00001")
        p2 = gen2.generate(patient_id="P00001")
        assert p1.first_name == p2.first_name
        assert p1.age == p2.age


class TestMockEHR:
    def test_query_patient(self):
        ehr = MockEHR(seed=42)
        assert ehr.patient_count == 100
        result = ehr.query_patient("P00000")
        assert result is not None
        assert "patient_id" in result

    def test_query_nonexistent_patient(self):
        ehr = MockEHR(seed=42)
        result = ehr.query_patient("NONEXISTENT")
        assert result is None

    def test_query_diagnoses(self):
        ehr = MockEHR(seed=42)
        diagnoses = ehr.query_diagnoses("P00000")
        assert isinstance(diagnoses, list)
        assert len(diagnoses) > 0

    def test_query_medications(self):
        ehr = MockEHR(seed=42)
        meds = ehr.query_medications("P00000")
        assert isinstance(meds, list)

    def test_audit_log(self):
        ehr = MockEHR(seed=42)
        assert len(ehr.audit_log) == 0
        ehr.query_patient("P00000")
        assert len(ehr.audit_log) == 1
        assert ehr.audit_log[0]["action"] == "query_patient"

    def test_write_encounter(self):
        ehr = MockEHR(seed=42)
        result = ehr.write_encounter("P00000", {"type": "office_visit"})
        assert result is True

    def test_order_lab(self):
        ehr = MockEHR(seed=42)
        result = ehr.order_lab("P00000", {"test": "CBC"})
        assert result["status"] == "completed"


class TestPayerRuleEngine:
    def test_check_prior_auth_required(self):
        engine = PayerRuleEngine()
        result = engine.check_prior_auth("medicare_traditional", "27447", {"age": 70})
        # Auth required but missing docs
        assert result.status in ("pending_review", "approved")

    def test_check_prior_auth_not_required(self):
        engine = PayerRuleEngine()
        result = engine.check_prior_auth("medicare_traditional", "70553", {})
        assert result.status == "approved"

    def test_validate_claim_valid(self):
        engine = PayerRuleEngine()
        result = engine.validate_claim(
            "medicare_traditional",
            [{"code": "99213"}],
            patient_age=50,
        )
        assert result.valid is True

    def test_validate_claim_bundling_error(self):
        engine = PayerRuleEngine()
        result = engine.validate_claim(
            "medicare_traditional",
            [{"code": "99395"}, {"code": "99213"}],
            patient_age=30,
        )
        assert result.valid is False
        assert len(result.errors) > 0

    def test_validate_claim_age_restriction(self):
        engine = PayerRuleEngine()
        result = engine.validate_claim(
            "medicare_traditional",
            [{"code": "99395"}],
            patient_age=50,  # 99395 is for 18-39
        )
        assert result.valid is False

    def test_get_rules_for_payer(self):
        engine = PayerRuleEngine()
        rules = engine.get_rules_for_payer("medicare_traditional")
        assert "auth_rules" in rules
        assert "claim_rules" in rules
        assert len(rules["auth_rules"]) > 0


class TestToolRegistry:
    def test_available_tools(self):
        registry = ToolRegistry()
        tools = registry.available_tools
        assert "ehr_query" in tools
        assert "escalate_to_human" in tools
        assert len(tools) == 21

    def test_call_ehr_query(self):
        registry = ToolRegistry()
        result = registry.call("ehr_query", patient_id="P00000", query_type="demographics")
        assert result.success is True
        assert result.data is not None

    def test_call_unknown_tool(self):
        registry = ToolRegistry()
        result = registry.call("nonexistent_tool")
        assert result.success is False
        assert "Unknown tool" in result.error

    def test_call_log(self):
        registry = ToolRegistry()
        registry.call("ehr_query", patient_id="P00000")
        registry.call("cpt_lookup", query="99213")
        assert len(registry.call_log) == 2

    def test_reset_clears_log(self):
        registry = ToolRegistry()
        registry.call("ehr_query", patient_id="P00000")
        registry.reset()
        assert len(registry.call_log) == 0

    def test_cpt_lookup(self):
        registry = ToolRegistry()
        result = registry.call("cpt_lookup", query="office visit")
        assert result.success is True
        assert len(result.data) > 0

    def test_icd10_search(self):
        registry = ToolRegistry()
        result = registry.call("icd10_search", query="diabetes")
        assert result.success is True
        assert len(result.data) > 0

    def test_escalate_to_human(self):
        registry = ToolRegistry()
        result = registry.call("escalate_to_human", reason="test escalation", urgency="high")
        assert result.success is True
        assert result.data["status"] == "escalated"

    def test_provider_search(self):
        registry = ToolRegistry()
        result = registry.call("provider_search", specialty="cardiology")
        assert result.success is True
        assert len(result.data) > 0

    def test_insurance_verify(self):
        registry = ToolRegistry()
        result = registry.call("insurance_verify", patient_id="P00000")
        assert result.success is True
