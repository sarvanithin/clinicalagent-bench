"""Configurable payer rule engine for prior authorization and claims validation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PriorAuthRule(BaseModel):
    """A single prior authorization rule."""

    rule_id: str
    payer: str
    procedure_codes: list[str] = Field(default_factory=list)
    diagnosis_codes: list[str] = Field(default_factory=list)
    requires_auth: bool = True
    documentation_required: list[str] = Field(default_factory=list)
    auto_approve_criteria: dict[str, Any] = Field(default_factory=dict)
    denial_reasons: list[str] = Field(default_factory=list)


class ClaimRule(BaseModel):
    """A claims processing rule."""

    rule_id: str
    payer: str
    code_type: str  # cpt, icd10, hcpcs
    code: str
    allowed_modifiers: list[str] = Field(default_factory=list)
    requires_medical_necessity: bool = False
    bundling_rules: list[str] = Field(default_factory=list)
    max_units: int | None = None
    age_restrictions: dict[str, int] = Field(default_factory=dict)


class AuthorizationResult(BaseModel):
    status: str  # approved, denied, pending_review
    reason: str = ""
    required_documentation: list[str] = Field(default_factory=list)


class ClaimValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PayerRuleEngine:
    """Configurable engine for payer-specific rules.

    Simulates the rule complexity that agents must navigate
    for prior authorization and claims submission.
    """

    def __init__(self) -> None:
        self._auth_rules: dict[str, list[PriorAuthRule]] = {}
        self._claim_rules: dict[str, list[ClaimRule]] = {}
        self._load_default_rules()

    def _load_default_rules(self) -> None:
        """Load a realistic set of default payer rules."""
        # Medicare Traditional rules
        medicare_auth = [
            PriorAuthRule(
                rule_id="MC-AUTH-001",
                payer="medicare_traditional",
                procedure_codes=["27447", "27130"],  # Knee/hip replacement
                requires_auth=True,
                documentation_required=[
                    "failed_conservative_treatment_6months",
                    "imaging_within_12months",
                    "bmi_documented",
                    "functional_assessment",
                ],
                auto_approve_criteria={"age_over": 65, "failed_pt_sessions": 12},
            ),
            PriorAuthRule(
                rule_id="MC-AUTH-002",
                payer="medicare_traditional",
                procedure_codes=["70553"],  # MRI Brain with/without contrast
                requires_auth=False,
            ),
            PriorAuthRule(
                rule_id="MC-AUTH-003",
                payer="medicare_traditional",
                procedure_codes=["J0585"],  # Botox injection
                diagnosis_codes=["G43.909", "G43.919"],  # Migraine
                requires_auth=True,
                documentation_required=[
                    "migraine_diary_3months",
                    "failed_2_preventive_medications",
                    "headache_days_per_month_gte_15",
                ],
            ),
        ]
        self._auth_rules["medicare_traditional"] = medicare_auth

        # UnitedHealthcare rules (more restrictive)
        uhc_auth = [
            PriorAuthRule(
                rule_id="UHC-AUTH-001",
                payer="commercial_united",
                procedure_codes=["27447", "27130"],
                requires_auth=True,
                documentation_required=[
                    "failed_conservative_treatment_3months",
                    "imaging_within_6months",
                    "bmi_under_40",
                    "functional_assessment",
                    "pain_management_consult",
                ],
                denial_reasons=[
                    "bmi_over_40_without_exception",
                    "insufficient_conservative_treatment",
                ],
            ),
            PriorAuthRule(
                rule_id="UHC-AUTH-002",
                payer="commercial_united",
                procedure_codes=["70553"],
                requires_auth=True,
                documentation_required=["clinical_indication", "prior_imaging_review"],
            ),
        ]
        self._auth_rules["commercial_united"] = uhc_auth

        # Medicare claim rules
        medicare_claims = [
            ClaimRule(
                rule_id="MC-CLM-001",
                payer="medicare_traditional",
                code_type="cpt",
                code="99213",
                allowed_modifiers=["25", "GT"],
                requires_medical_necessity=False,
                max_units=1,
            ),
            ClaimRule(
                rule_id="MC-CLM-002",
                payer="medicare_traditional",
                code_type="cpt",
                code="99214",
                allowed_modifiers=["25", "GT"],
                requires_medical_necessity=True,
                max_units=1,
            ),
            ClaimRule(
                rule_id="MC-CLM-003",
                payer="medicare_traditional",
                code_type="cpt",
                code="99395",
                bundling_rules=["cannot_bill_with_99213", "cannot_bill_with_99214"],
                age_restrictions={"min_age": 18, "max_age": 39},
                max_units=1,
            ),
            ClaimRule(
                rule_id="MC-CLM-004",
                payer="medicare_traditional",
                code_type="cpt",
                code="99396",
                bundling_rules=["cannot_bill_with_99213", "cannot_bill_with_99214"],
                age_restrictions={"min_age": 40, "max_age": 64},
                max_units=1,
            ),
        ]
        self._claim_rules["medicare_traditional"] = medicare_claims

    def check_prior_auth(
        self, payer: str, procedure_code: str, patient_data: dict[str, Any]
    ) -> AuthorizationResult:
        """Check if a procedure requires prior authorization and validate."""
        rules = self._auth_rules.get(payer, [])
        matching = [r for r in rules if procedure_code in r.procedure_codes]

        if not matching:
            return AuthorizationResult(status="approved", reason="No auth rule found")

        rule = matching[0]
        if not rule.requires_auth:
            return AuthorizationResult(status="approved", reason="Auth not required")

        missing_docs = []
        for doc in rule.documentation_required:
            if doc not in patient_data.get("documentation", {}):
                missing_docs.append(doc)

        if missing_docs:
            return AuthorizationResult(
                status="pending_review",
                reason="Missing required documentation",
                required_documentation=missing_docs,
            )

        # Check auto-approve criteria
        criteria = rule.auto_approve_criteria
        if criteria:
            age = patient_data.get("age", 0)
            if "age_over" in criteria and age >= criteria["age_over"]:
                return AuthorizationResult(status="approved", reason="Auto-approved by age")

        return AuthorizationResult(status="pending_review", reason="Manual review required")

    def validate_claim(
        self, payer: str, codes: list[dict[str, str]], patient_age: int
    ) -> ClaimValidationResult:
        """Validate a set of claim codes against payer rules."""
        rules = self._claim_rules.get(payer, [])
        errors: list[str] = []
        warnings: list[str] = []

        submitted_codes = [c["code"] for c in codes]

        for code_entry in codes:
            code = code_entry["code"]
            modifier = code_entry.get("modifier")

            matching = [r for r in rules if r.code == code]
            if not matching:
                continue

            rule = matching[0]

            if modifier and modifier not in rule.allowed_modifiers:
                errors.append(f"Invalid modifier {modifier} for code {code}")

            if rule.age_restrictions:
                min_age = rule.age_restrictions.get("min_age", 0)
                max_age = rule.age_restrictions.get("max_age", 999)
                if not min_age <= patient_age <= max_age:
                    errors.append(
                        f"Code {code} age restriction: {min_age}-{max_age}, patient is {patient_age}"
                    )

            for bundle_rule in rule.bundling_rules:
                blocked_code = bundle_rule.replace("cannot_bill_with_", "")
                if blocked_code in submitted_codes:
                    errors.append(f"Code {code} cannot be billed with {blocked_code}")

        return ClaimValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def get_rules_for_payer(self, payer: str) -> dict[str, Any]:
        """Get all rules for a specific payer (for agent reference)."""
        return {
            "auth_rules": [r.model_dump() for r in self._auth_rules.get(payer, [])],
            "claim_rules": [r.model_dump() for r in self._claim_rules.get(payer, [])],
        }

    def add_auth_rule(self, rule: PriorAuthRule) -> None:
        """Add a custom prior auth rule."""
        self._auth_rules.setdefault(rule.payer, []).append(rule)

    def add_claim_rule(self, rule: ClaimRule) -> None:
        """Add a custom claim rule."""
        self._claim_rules.setdefault(rule.payer, []).append(rule)
