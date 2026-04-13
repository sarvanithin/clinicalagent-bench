"""Synthea integration for importing large-scale synthetic patient cohorts.

Loads FHIR Bundle JSON files exported by Synthea
(https://github.com/synthetichealth/synthea) and converts them into the
internal Patient model used by the MockEHR.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from clinicalagent_bench.virtual_env.patient import (
    Diagnosis,
    Encounter,
    InsuranceInfo,
    Medication,
    Patient,
)

logger = logging.getLogger(__name__)


class SyntheaImporter:
    """Import Synthea-generated FHIR Bundles into ClinicalAgent-Bench patients.

    Synthea produces one FHIR Bundle JSON per patient containing Patient,
    Condition, MedicationRequest, Encounter, Observation, and Coverage
    resources. This importer extracts the relevant fields and maps them
    to the internal data model.

    Usage:
        importer = SyntheaImporter()
        patients = importer.load_directory("/path/to/synthea/output/fhir")
    """

    def __init__(self, default_payer: str = "medicare_traditional") -> None:
        self._default_payer = default_payer

    def load_directory(self, path: str | Path) -> list[Patient]:
        """Load all FHIR Bundle JSON files from a Synthea output directory.

        Args:
            path: Directory containing *.json FHIR Bundle files.

        Returns:
            List of Patient objects ready for MockEHR.
        """
        directory = Path(path)
        if not directory.is_dir():
            raise FileNotFoundError(f"Synthea output directory not found: {path}")

        patients = []
        json_files = sorted(directory.glob("*.json"))
        logger.info("Found %d JSON files in %s", len(json_files), directory)

        for filepath in json_files:
            try:
                patient = self.load_bundle(filepath)
                if patient:
                    patients.append(patient)
            except Exception as e:
                logger.warning("Skipping %s: %s", filepath.name, e)

        logger.info("Imported %d patients from Synthea", len(patients))
        return patients

    def load_bundle(self, filepath: str | Path) -> Patient | None:
        """Load a single FHIR Bundle JSON and convert to Patient.

        Args:
            filepath: Path to a Synthea FHIR Bundle JSON file.

        Returns:
            Patient object, or None if the bundle has no Patient resource.
        """
        with open(filepath) as f:
            bundle = json.load(f)

        if bundle.get("resourceType") != "Bundle":
            return None

        entries = bundle.get("entry", [])
        resources_by_type: dict[str, list[dict[str, Any]]] = {}
        for entry in entries:
            resource = entry.get("resource", {})
            rtype = resource.get("resourceType", "")
            resources_by_type.setdefault(rtype, []).append(resource)

        patient_resources = resources_by_type.get("Patient", [])
        if not patient_resources:
            return None

        return self._convert_patient(patient_resources[0], resources_by_type)

    def _convert_patient(
        self,
        patient_res: dict[str, Any],
        resources: dict[str, list[dict[str, Any]]],
    ) -> Patient:
        """Convert FHIR resources into internal Patient model."""
        patient_id = patient_res.get("id", "unknown")

        # Name
        names = patient_res.get("name", [{}])
        name_obj = names[0] if names else {}
        given = " ".join(name_obj.get("given", ["Unknown"]))
        family = name_obj.get("family", "Patient")
        full_name = f"{given} {family}"

        # Demographics
        birth_date = patient_res.get("birthDate", "1960-01-01")
        gender = patient_res.get("gender", "unknown")
        age = self._compute_age(birth_date)

        # Race/Ethnicity from extensions
        race = "unknown"
        ethnicity = "unknown"
        for ext in patient_res.get("extension", []):
            url = ext.get("url", "")
            if "us-core-race" in url:
                race = self._extract_extension_display(ext)
            elif "us-core-ethnicity" in url:
                ethnicity = self._extract_extension_display(ext)

        # Address
        addresses = patient_res.get("address", [{}])
        addr = addresses[0] if addresses else {}
        city = addr.get("city", "")
        state = addr.get("state", "")

        # Diagnoses from Conditions
        diagnoses = []
        for cond in resources.get("Condition", []):
            code_obj = cond.get("code", {})
            codings = code_obj.get("coding", [{}])
            coding = codings[0] if codings else {}
            diagnoses.append(
                Diagnosis(
                    icd10_code=coding.get("code", ""),
                    description=coding.get("display", code_obj.get("text", "")),
                    date_diagnosed=cond.get("onsetDateTime", "")[:10],
                    status=cond.get("clinicalStatus", {})
                    .get("coding", [{}])[0]
                    .get("code", "active"),
                )
            )

        # Medications from MedicationRequests
        medications = []
        for med in resources.get("MedicationRequest", []):
            code_obj = med.get("medicationCodeableConcept", {})
            codings = code_obj.get("coding", [{}])
            coding = codings[0] if codings else {}
            dosage = med.get("dosageInstruction", [{}])
            dose_text = dosage[0].get("text", "") if dosage else ""
            medications.append(
                Medication(
                    name=coding.get("display", code_obj.get("text", "")),
                    dosage=dose_text or "as directed",
                    frequency="as prescribed",
                    start_date=med.get("authoredOn", "")[:10],
                    active=med.get("status", "") == "active",
                )
            )

        # Encounters
        encounters = []
        for enc in resources.get("Encounter", []):
            type_list = enc.get("type", [{}])
            enc_type = type_list[0] if type_list else {}
            codings = enc_type.get("coding", [{}])
            coding = codings[0] if codings else {}
            period = enc.get("period", {})
            encounters.append(
                Encounter(
                    date=period.get("start", "")[:10],
                    type=coding.get("display", "office visit"),
                    provider="Synthea Provider",
                    notes=f"FHIR Encounter {enc.get('id', '')}",
                    diagnoses=[],
                )
            )

        # Vitals from Observations
        vitals: dict[str, float] = {}
        for obs in resources.get("Observation", []):
            code_obj = obs.get("code", {})
            codings = code_obj.get("coding", [{}])
            coding = codings[0] if codings else {}
            display = coding.get("display", "").lower()
            value = obs.get("valueQuantity", {}).get("value")
            if value is not None:
                if "systolic" in display:
                    vitals["blood_pressure_systolic"] = float(value)
                elif "diastolic" in display:
                    vitals["blood_pressure_diastolic"] = float(value)
                elif "heart rate" in display:
                    vitals["heart_rate"] = float(value)
                elif "temperature" in display:
                    vitals["temperature"] = float(value)
                elif "oxygen" in display or "spo2" in display:
                    vitals["oxygen_saturation"] = float(value)
                elif "respiratory" in display:
                    vitals["respiratory_rate"] = float(value)
                elif "body mass" in display or "bmi" in display:
                    vitals["bmi"] = float(value)
                elif "weight" in display.split():
                    vitals["weight_kg"] = float(value)
                elif "height" in display.split():
                    vitals["height_cm"] = float(value)

        # Insurance from Coverage
        insurance = None
        coverages = resources.get("Coverage", [])
        if coverages:
            cov = coverages[0]
            type_obj = cov.get("type", {})
            type_codings = type_obj.get("coding", [{}])
            type_coding = type_codings[0] if type_codings else {}
            payer_name = type_coding.get("display", self._default_payer)
            insurance = InsuranceInfo(
                payer=self._map_payer(payer_name),
                plan_id=cov.get("id", ""),
                group_number="",
                member_id=patient_id,
                coverage_type=type_coding.get("code", ""),
            )

        if not insurance:
            insurance = InsuranceInfo(
                payer=self._default_payer,
                plan_id="synthea-default",
                group_number="",
                member_id=patient_id,
                coverage_type="PPO",
            )

        return Patient(
            patient_id=f"synthea-{patient_id[:12]}",
            name=full_name,
            age=age,
            gender=gender,
            race=race,
            ethnicity=ethnicity,
            primary_language="English",
            diagnoses=diagnoses[:20],
            medications=medications[:20],
            encounters=encounters[:10],
            vitals=vitals,
            insurance=insurance,
            allergies=[],
        )

    @staticmethod
    def _compute_age(birth_date: str) -> int:
        """Approximate age from birth date string."""
        try:
            year = int(birth_date[:4])
            return max(0, 2026 - year)
        except (ValueError, IndexError):
            return 65

    @staticmethod
    def _extract_extension_display(ext: dict[str, Any]) -> str:
        """Extract display text from a FHIR extension with nested coding."""
        for sub_ext in ext.get("extension", []):
            coding = sub_ext.get("valueCoding", {})
            display = coding.get("display")
            if display:
                return display
        return "unknown"

    @staticmethod
    def _map_payer(payer_name: str) -> str:
        """Map Synthea payer names to internal payer identifiers."""
        name_lower = payer_name.lower()
        if "medicare" in name_lower:
            return "medicare_traditional"
        if "medicaid" in name_lower:
            return "medicaid"
        if "united" in name_lower:
            return "unitedhealthcare"
        if "aetna" in name_lower:
            return "aetna"
        if "cigna" in name_lower:
            return "cigna"
        if "blue" in name_lower or "bcbs" in name_lower:
            return "bcbs"
        if "anthem" in name_lower:
            return "anthem"
        return "medicare_traditional"
