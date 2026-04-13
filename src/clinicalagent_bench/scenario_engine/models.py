"""Pydantic models for clinical benchmark scenarios."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Domain(str, Enum):
    BILLING_CODING = "billing_coding"
    TRIAGE_SCHEDULING = "triage_scheduling"
    CLINICAL_DOCUMENTATION = "clinical_documentation"
    PRIOR_AUTHORIZATION = "prior_authorization"
    CARE_NAVIGATION = "care_navigation"
    CLINICAL_REASONING = "clinical_reasoning"
    MULTI_AGENT = "multi_agent"
    REFUSAL_ESCALATION = "refusal_escalation"
    BIAS_VALIDATION = "bias_validation"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class RiskLevel(str, Enum):
    PATIENT_SAFETY = "patient_safety"
    FINANCIAL = "financial"
    COMPLIANCE = "compliance"
    OPERATIONAL = "operational"


class Payer(str, Enum):
    MEDICARE_TRADITIONAL = "medicare_traditional"
    MEDICARE_ADVANTAGE = "medicare_advantage"
    MEDICAID = "medicaid"
    COMMERCIAL_UNITED = "commercial_united"
    COMMERCIAL_AETNA = "commercial_aetna"
    COMMERCIAL_CIGNA = "commercial_cigna"
    COMMERCIAL_BCBS = "commercial_bcbs"
    SELF_PAY = "self_pay"


class ToolName(str, Enum):
    EHR_QUERY = "ehr_query"
    EHR_WRITE = "ehr_write"
    CPT_LOOKUP = "cpt_lookup"
    ICD10_SEARCH = "icd10_search"
    CLAIM_SUBMIT = "claim_submit"
    CLAIM_STATUS = "claim_status"
    PAYER_RULES = "payer_rules"
    PRIOR_AUTH_SUBMIT = "prior_auth_submit"
    PRIOR_AUTH_STATUS = "prior_auth_status"
    LAB_ORDER = "lab_order"
    LAB_RESULTS = "lab_results"
    PHARMACY_CHECK = "pharmacy_check"
    PRESCRIPTION_WRITE = "prescription_write"
    SCHEDULING_QUERY = "scheduling_query"
    SCHEDULING_BOOK = "scheduling_book"
    REFERRAL_SUBMIT = "referral_submit"
    PROVIDER_SEARCH = "provider_search"
    PATIENT_HISTORY = "patient_history"
    INSURANCE_VERIFY = "insurance_verify"
    DOCUMENTATION_GENERATE = "documentation_generate"
    ESCALATE_TO_HUMAN = "escalate_to_human"


class ScenarioInput(BaseModel):
    """The input context provided to the agent for a scenario."""

    patient_context: str = Field(description="Clinical context about the patient")
    available_tools: list[ToolName] = Field(description="Tools the agent can use")
    payer: Payer | None = Field(default=None, description="Insurance payer if relevant")
    additional_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Domain-specific additional context (e.g., prior notes, lab results)",
    )


class ExpectedAction(BaseModel):
    """An expected action the agent should take."""

    step: int = Field(description="Order of the action in the workflow")
    action: str = Field(description="The action to perform (tool call or decision)")
    tool: ToolName | None = Field(default=None, description="Expected tool to use")
    expected_output: dict[str, Any] | None = Field(
        default=None, description="Expected output values (e.g., codes, text)"
    )
    required: bool = Field(default=True, description="Whether this step is required")
    partial_credit: bool = Field(
        default=False, description="Allow partial credit for close answers"
    )
    alternatives: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Clinically acceptable alternative outputs",
    )


class SafetyConstraint(BaseModel):
    """A safety constraint that the agent must respect."""

    constraint: str = Field(description="Description of the safety constraint")
    severity: str = Field(
        default="critical",
        description="Severity if violated: critical, high, medium, low",
    )
    consequence_weight: float = Field(
        default=1.0,
        description="Multiplier for how bad violating this constraint is (1.0 = standard)",
    )


class EscalationTrigger(BaseModel):
    """A condition under which the agent should escalate to a human."""

    condition: str = Field(description="The condition that triggers escalation")
    expected_action: str = Field(description="What the agent should do when triggered")
    is_hidden: bool = Field(
        default=False,
        description="If true, the condition is embedded in data, not stated explicitly",
    )


class EdgeCase(BaseModel):
    """An edge case variation of the scenario."""

    description: str = Field(description="Description of the edge case")
    modified_input: dict[str, Any] = Field(
        default_factory=dict,
        description="How the input changes for this edge case",
    )
    expected_change: str = Field(
        default="",
        description="How the expected behavior changes",
    )


class ScoringConfig(BaseModel):
    """Scoring weights for a specific scenario."""

    accuracy_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    safety_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    completeness_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    efficiency_weight: float = Field(default=0.1, ge=0.0, le=1.0)


class Scenario(BaseModel):
    """A complete clinical benchmark scenario."""

    scenario_id: str = Field(description="Unique scenario identifier (e.g., billing-001)")
    name: str = Field(description="Human-readable scenario name")
    description: str = Field(description="What this scenario tests")
    domain: Domain
    difficulty: Difficulty
    risk_level: RiskLevel
    input: ScenarioInput
    expected_actions: list[ExpectedAction] = Field(min_length=1)
    safety_constraints: list[SafetyConstraint] = Field(default_factory=list)
    escalation_triggers: list[EscalationTrigger] = Field(default_factory=list)
    edge_cases: list[EdgeCase] = Field(default_factory=list)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    tags: list[str] = Field(default_factory=list)
    version: str = Field(default="1.0")
