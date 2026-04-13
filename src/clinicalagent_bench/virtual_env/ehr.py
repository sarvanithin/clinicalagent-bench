"""Mock FHIR-compliant Electronic Health Record system."""

from __future__ import annotations

from typing import Any

from clinicalagent_bench.virtual_env.patient import Patient, PatientGenerator


class MockEHR:
    """Simulated EHR that agents interact with during benchmarks.

    Provides FHIR-like query/write operations against synthetic patient data.
    All mutations are tracked for scoring.
    """

    def __init__(self, patients: list[Patient] | None = None, seed: int = 42) -> None:
        if patients:
            self._patients = {p.patient_id: p for p in patients}
        else:
            gen = PatientGenerator(seed=seed)
            cohort = gen.generate_cohort(100)
            self._patients = {p.patient_id: p for p in cohort}
        self._audit_log: list[dict[str, Any]] = []

    @property
    def patient_count(self) -> int:
        return len(self._patients)

    @property
    def audit_log(self) -> list[dict[str, Any]]:
        return list(self._audit_log)

    def _log(self, action: str, patient_id: str, details: dict[str, Any]) -> None:
        self._audit_log.append({
            "action": action,
            "patient_id": patient_id,
            "details": details,
        })

    def query_patient(self, patient_id: str) -> dict[str, Any] | None:
        """Query patient demographics and basic info."""
        patient = self._patients.get(patient_id)
        if not patient:
            return None
        self._log("query_patient", patient_id, {})
        return patient.model_dump(include={
            "patient_id", "first_name", "last_name", "date_of_birth",
            "age", "sex", "race", "ethnicity", "language", "allergies",
        })

    def query_diagnoses(self, patient_id: str) -> list[dict[str, Any]]:
        """Query patient's active diagnoses."""
        patient = self._patients.get(patient_id)
        if not patient:
            return []
        self._log("query_diagnoses", patient_id, {})
        return [d.model_dump() for d in patient.diagnoses]

    def query_medications(self, patient_id: str) -> list[dict[str, Any]]:
        """Query patient's current medications."""
        patient = self._patients.get(patient_id)
        if not patient:
            return []
        self._log("query_medications", patient_id, {})
        return [m.model_dump() for m in patient.medications]

    def query_encounters(self, patient_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Query patient's recent encounters."""
        patient = self._patients.get(patient_id)
        if not patient:
            return []
        self._log("query_encounters", patient_id, {"limit": limit})
        return [e.model_dump() for e in patient.encounters[:limit]]

    def query_vitals(self, patient_id: str) -> dict[str, Any]:
        """Query patient's most recent vitals."""
        patient = self._patients.get(patient_id)
        if not patient:
            return {}
        self._log("query_vitals", patient_id, {})
        return patient.vitals

    def query_insurance(self, patient_id: str) -> dict[str, Any] | None:
        """Query patient's insurance information."""
        patient = self._patients.get(patient_id)
        if not patient or not patient.insurance:
            return None
        self._log("query_insurance", patient_id, {})
        return patient.insurance.model_dump()

    def write_encounter(self, patient_id: str, encounter: dict[str, Any]) -> bool:
        """Write a new encounter to the patient's record."""
        patient = self._patients.get(patient_id)
        if not patient:
            return False
        self._log("write_encounter", patient_id, encounter)
        return True

    def write_diagnosis(self, patient_id: str, diagnosis: dict[str, Any]) -> bool:
        """Add a diagnosis to the patient's record."""
        patient = self._patients.get(patient_id)
        if not patient:
            return False
        self._log("write_diagnosis", patient_id, diagnosis)
        return True

    def write_prescription(self, patient_id: str, prescription: dict[str, Any]) -> bool:
        """Write a prescription order."""
        patient = self._patients.get(patient_id)
        if not patient:
            return False
        self._log("write_prescription", patient_id, prescription)
        return True

    def order_lab(self, patient_id: str, lab_order: dict[str, Any]) -> dict[str, Any]:
        """Submit a lab order and return mock results."""
        patient = self._patients.get(patient_id)
        if not patient:
            return {"error": "Patient not found"}
        self._log("order_lab", patient_id, lab_order)
        return {
            "order_id": f"LAB-{patient_id}-{len(self._audit_log)}",
            "status": "completed",
            "results": lab_order.get("mock_results", {}),
        }

    def submit_referral(self, patient_id: str, referral: dict[str, Any]) -> dict[str, Any]:
        """Submit a referral."""
        self._log("submit_referral", patient_id, referral)
        return {
            "referral_id": f"REF-{patient_id}-{len(self._audit_log)}",
            "status": "submitted",
        }
