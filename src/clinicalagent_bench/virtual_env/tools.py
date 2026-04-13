"""Tool simulation layer for agent interactions with the virtual clinical environment."""

from __future__ import annotations

from typing import Any

from clinicalagent_bench.virtual_env.ehr import MockEHR
from clinicalagent_bench.virtual_env.payer_rules import PayerRuleEngine


class ToolResult(dict[str, Any]):
    """Result from a tool call, with success tracking."""

    def __init__(self, success: bool, data: Any = None, error: str = "") -> None:
        super().__init__(success=success, data=data, error=error)
        self.success = success
        self.data = data
        self.error = error


class ToolRegistry:
    """Registry of available tools that agents can call during scenarios.

    Each tool wraps a function in the virtual clinical environment.
    Tool calls are logged for scoring.
    """

    def __init__(self, ehr: MockEHR | None = None, payer_engine: PayerRuleEngine | None = None):
        self._ehr = ehr or MockEHR()
        self._payer = payer_engine or PayerRuleEngine()
        self._call_log: list[dict[str, Any]] = []
        self._tools: dict[str, Any] = self._build_tool_map()

    def _build_tool_map(self) -> dict[str, Any]:
        return {
            "ehr_query": self._ehr_query,
            "ehr_write": self._ehr_write,
            "cpt_lookup": self._cpt_lookup,
            "icd10_search": self._icd10_search,
            "claim_submit": self._claim_submit,
            "claim_status": self._claim_status,
            "payer_rules": self._payer_rules,
            "prior_auth_submit": self._prior_auth_submit,
            "prior_auth_status": self._prior_auth_status,
            "lab_order": self._lab_order,
            "lab_results": self._lab_results,
            "pharmacy_check": self._pharmacy_check,
            "prescription_write": self._prescription_write,
            "scheduling_query": self._scheduling_query,
            "scheduling_book": self._scheduling_book,
            "referral_submit": self._referral_submit,
            "provider_search": self._provider_search,
            "patient_history": self._patient_history,
            "insurance_verify": self._insurance_verify,
            "documentation_generate": self._documentation_generate,
            "escalate_to_human": self._escalate_to_human,
        }

    @property
    def call_log(self) -> list[dict[str, Any]]:
        return list(self._call_log)

    @property
    def available_tools(self) -> list[str]:
        return list(self._tools.keys())

    def call(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """Call a tool by name with arguments."""
        self._call_log.append({"tool": tool_name, "args": kwargs})

        handler = self._tools.get(tool_name)
        if not handler:
            return ToolResult(success=False, error=f"Unknown tool: {tool_name}")

        try:
            result = handler(**kwargs)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def reset(self) -> None:
        """Clear call log for a new scenario run."""
        self._call_log.clear()

    # --- Tool implementations ---

    def _ehr_query(self, patient_id: str, query_type: str = "demographics", **kw: Any) -> Any:
        dispatch = {
            "demographics": self._ehr.query_patient,
            "diagnoses": self._ehr.query_diagnoses,
            "medications": self._ehr.query_medications,
            "encounters": self._ehr.query_encounters,
            "vitals": self._ehr.query_vitals,
            "insurance": self._ehr.query_insurance,
        }
        handler = dispatch.get(query_type)
        if not handler:
            return {"error": f"Unknown query type: {query_type}"}
        return handler(patient_id)

    def _ehr_write(self, patient_id: str, write_type: str, data: dict[str, Any], **kw: Any) -> Any:
        dispatch = {
            "encounter": self._ehr.write_encounter,
            "diagnosis": self._ehr.write_diagnosis,
            "prescription": self._ehr.write_prescription,
        }
        handler = dispatch.get(write_type)
        if not handler:
            return {"error": f"Unknown write type: {write_type}"}
        return handler(patient_id, data)

    def _cpt_lookup(self, query: str, **kw: Any) -> list[dict[str, str]]:
        cpt_db = {
            "99213": "Office visit, established, low complexity",
            "99214": "Office visit, established, moderate complexity",
            "99215": "Office visit, established, high complexity",
            "99395": "Preventive visit, established, 18-39",
            "99396": "Preventive visit, established, 40-64",
            "97597": "Wound care debridement, first 20 sq cm",
            "27447": "Total knee replacement",
            "27130": "Total hip replacement",
            "70553": "MRI brain with/without contrast",
            "99441": "Telephone E/M, 5-10 minutes",
            "99442": "Telephone E/M, 11-20 minutes",
        }
        results = []
        for code, desc in cpt_db.items():
            if query.lower() in code.lower() or query.lower() in desc.lower():
                results.append({"code": code, "description": desc})
        return results

    def _icd10_search(self, query: str, **kw: Any) -> list[dict[str, str]]:
        icd10_db = {
            "E11.9": "Type 2 diabetes mellitus without complications",
            "E11.65": "Type 2 diabetes mellitus with hyperglycemia",
            "I10": "Essential hypertension",
            "I25.10": "Atherosclerotic heart disease",
            "J45.20": "Mild intermittent asthma, uncomplicated",
            "M54.5": "Low back pain",
            "F32.1": "Major depressive disorder, single episode, moderate",
            "K21.0": "GERD with esophagitis",
            "L97.529": "Non-pressure chronic ulcer of other part of left foot",
            "G43.909": "Migraine, unspecified, not intractable",
            "Z00.00": "Encounter for general adult medical examination",
        }
        results = []
        for code, desc in icd10_db.items():
            if query.lower() in code.lower() or query.lower() in desc.lower():
                results.append({"code": code, "description": desc})
        return results

    def _claim_submit(self, payer: str, codes: list[dict[str, str]], patient_age: int, **kw: Any) -> Any:
        result = self._payer.validate_claim(payer, codes, patient_age)
        return result.model_dump()

    def _claim_status(self, claim_id: str, **kw: Any) -> dict[str, str]:
        return {"claim_id": claim_id, "status": "pending", "estimated_days": "14"}

    def _payer_rules(self, payer: str, **kw: Any) -> Any:
        return self._payer.get_rules_for_payer(payer)

    def _prior_auth_submit(
        self, payer: str, procedure_code: str, patient_data: dict[str, Any], **kw: Any
    ) -> Any:
        result = self._payer.check_prior_auth(payer, procedure_code, patient_data)
        return result.model_dump()

    def _prior_auth_status(self, auth_id: str, **kw: Any) -> dict[str, str]:
        return {"auth_id": auth_id, "status": "pending_review"}

    def _lab_order(self, patient_id: str, lab_order: dict[str, Any], **kw: Any) -> Any:
        return self._ehr.order_lab(patient_id, lab_order)

    def _lab_results(self, order_id: str, **kw: Any) -> dict[str, Any]:
        return {"order_id": order_id, "status": "completed", "results": {}}

    def _pharmacy_check(self, patient_id: str, medication: str, **kw: Any) -> dict[str, Any]:
        meds = self._ehr.query_medications(patient_id)
        interactions = []
        for m in meds:
            if isinstance(m, dict) and m.get("name", "").lower() != medication.lower():
                interactions.append({"drug": m["name"], "severity": "low", "description": "Monitor"})
        return {"medication": medication, "interactions": interactions, "covered": True}

    def _prescription_write(self, patient_id: str, prescription: dict[str, Any], **kw: Any) -> Any:
        return self._ehr.write_prescription(patient_id, prescription)

    def _scheduling_query(self, provider_id: str = "", specialty: str = "", **kw: Any) -> list[dict[str, str]]:
        return [
            {"slot_id": "S001", "date": "2026-04-15", "time": "09:00", "provider": provider_id or "Dr. Smith"},
            {"slot_id": "S002", "date": "2026-04-15", "time": "14:00", "provider": provider_id or "Dr. Smith"},
            {"slot_id": "S003", "date": "2026-04-16", "time": "10:30", "provider": provider_id or "Dr. Jones"},
        ]

    def _scheduling_book(self, slot_id: str, patient_id: str, **kw: Any) -> dict[str, str]:
        return {"appointment_id": f"APT-{slot_id}-{patient_id}", "status": "confirmed"}

    def _referral_submit(self, patient_id: str, referral: dict[str, Any], **kw: Any) -> Any:
        return self._ehr.submit_referral(patient_id, referral)

    def _provider_search(self, specialty: str = "", location: str = "", **kw: Any) -> list[dict[str, Any]]:
        return [
            {"provider_id": "PRV001", "name": "Dr. Sarah Chen", "specialty": specialty or "Internal Medicine",
             "distance_miles": 2.1, "rating": 4.8, "accepting_new": True},
            {"provider_id": "PRV002", "name": "Dr. James Wilson", "specialty": specialty or "Internal Medicine",
             "distance_miles": 5.3, "rating": 4.5, "accepting_new": True},
        ]

    def _patient_history(self, patient_id: str, **kw: Any) -> dict[str, Any]:
        demographics = self._ehr.query_patient(patient_id) or {}
        diagnoses = self._ehr.query_diagnoses(patient_id)
        medications = self._ehr.query_medications(patient_id)
        vitals = self._ehr.query_vitals(patient_id)
        return {
            "demographics": demographics,
            "diagnoses": diagnoses,
            "medications": medications,
            "vitals": vitals,
        }

    def _insurance_verify(self, patient_id: str, **kw: Any) -> dict[str, Any]:
        info = self._ehr.query_insurance(patient_id)
        if not info:
            return {"verified": False, "reason": "No insurance on file"}
        return {"verified": True, "insurance": info, "eligible": True}

    def _documentation_generate(self, template: str, patient_id: str, encounter_data: dict[str, Any] | None = None, **kw: Any) -> dict[str, str]:
        return {
            "document_id": f"DOC-{patient_id}-{template}",
            "template": template,
            "status": "draft",
            "content": f"[Generated {template} documentation for patient {patient_id}]",
        }

    def _escalate_to_human(self, reason: str, urgency: str = "normal", context: dict[str, Any] | None = None, **kw: Any) -> dict[str, str]:
        return {
            "escalation_id": f"ESC-{len(self._call_log)}",
            "status": "escalated",
            "reason": reason,
            "urgency": urgency,
        }
