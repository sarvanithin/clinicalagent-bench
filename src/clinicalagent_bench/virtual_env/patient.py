"""Synthetic patient data models and generator."""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel, Field


class Medication(BaseModel):
    name: str
    dosage: str
    frequency: str
    start_date: str
    prescriber: str


class Diagnosis(BaseModel):
    icd10_code: str
    description: str
    date_diagnosed: str
    status: str = "active"  # active, resolved, chronic


class Encounter(BaseModel):
    encounter_id: str
    date: str
    type: str  # office_visit, emergency, telehealth, inpatient
    provider: str
    chief_complaint: str
    diagnoses: list[Diagnosis] = Field(default_factory=list)
    notes: str = ""


class InsuranceInfo(BaseModel):
    payer: str
    plan_id: str
    member_id: str
    group_number: str
    effective_date: str
    copay: float = 0.0
    deductible: float = 0.0
    deductible_met: float = 0.0


class Patient(BaseModel):
    patient_id: str
    first_name: str
    last_name: str
    date_of_birth: str
    age: int
    sex: str
    race: str
    ethnicity: str
    language: str = "English"
    insurance: InsuranceInfo | None = None
    medications: list[Medication] = Field(default_factory=list)
    diagnoses: list[Diagnosis] = Field(default_factory=list)
    encounters: list[Encounter] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    vitals: dict[str, Any] = Field(default_factory=dict)


class PatientGenerator:
    """Generates synthetic patient data for benchmark scenarios."""

    FIRST_NAMES = [
        "James",
        "Maria",
        "Robert",
        "Jennifer",
        "Michael",
        "Linda",
        "David",
        "Patricia",
        "William",
        "Elizabeth",
        "Chen",
        "Aisha",
        "Raj",
        "Fatima",
        "Hiroshi",
        "Olga",
        "Ahmed",
        "Priya",
        "Carlos",
        "Yuki",
    ]
    LAST_NAMES = [
        "Smith",
        "Garcia",
        "Johnson",
        "Williams",
        "Brown",
        "Jones",
        "Miller",
        "Davis",
        "Rodriguez",
        "Martinez",
        "Patel",
        "Kim",
        "Nguyen",
        "Chen",
        "Ali",
        "Singh",
        "Tanaka",
        "Ivanova",
        "Okafor",
        "Müller",
    ]
    COMMON_DIAGNOSES = [
        ("E11.9", "Type 2 diabetes mellitus without complications"),
        ("I10", "Essential hypertension"),
        ("J45.20", "Mild intermittent asthma, uncomplicated"),
        ("E78.5", "Hyperlipidemia, unspecified"),
        ("M54.5", "Low back pain"),
        ("F32.1", "Major depressive disorder, single episode, moderate"),
        ("K21.0", "Gastro-esophageal reflux disease with esophagitis"),
        ("G47.33", "Obstructive sleep apnea"),
        ("N18.3", "Chronic kidney disease, stage 3"),
        ("J44.1", "COPD with acute exacerbation"),
    ]
    COMMON_MEDICATIONS = [
        ("Metformin", "500mg", "twice daily"),
        ("Lisinopril", "10mg", "once daily"),
        ("Atorvastatin", "20mg", "once daily at bedtime"),
        ("Amlodipine", "5mg", "once daily"),
        ("Omeprazole", "20mg", "once daily before breakfast"),
        ("Albuterol", "90mcg", "as needed"),
        ("Sertraline", "50mg", "once daily"),
        ("Metoprolol", "25mg", "twice daily"),
    ]
    PAYERS = [
        ("Medicare Traditional", "MCARE-STD", "MC"),
        ("Medicare Advantage - UHC", "MA-UHC-PPO", "MA"),
        ("Medicaid", "MCAID-STD", "MD"),
        ("UnitedHealthcare", "UHC-PPO-500", "UH"),
        ("Aetna", "AETNA-HMO-250", "AE"),
        ("Cigna", "CIGNA-PPO-1000", "CI"),
        ("BCBS", "BCBS-PPO-750", "BC"),
    ]

    def __init__(self, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    def generate(self, patient_id: str | None = None, **overrides: Any) -> Patient:
        """Generate a single synthetic patient."""
        pid = patient_id or f"P{self._rng.randint(10000, 99999)}"
        age = overrides.get("age", self._rng.randint(18, 90))
        dob = date.today() - timedelta(days=age * 365 + self._rng.randint(0, 364))

        payer_name, plan_id, prefix = self._rng.choice(self.PAYERS)
        insurance = InsuranceInfo(
            payer=payer_name,
            plan_id=plan_id,
            member_id=f"{prefix}{self._rng.randint(100000, 999999)}",
            group_number=f"GRP{self._rng.randint(1000, 9999)}",
            effective_date=str(date.today() - timedelta(days=self._rng.randint(30, 730))),
            copay=self._rng.choice([0, 20, 30, 40, 50]),
            deductible=self._rng.choice([0, 250, 500, 1000, 2000]),
            deductible_met=self._rng.uniform(0, 1) * 2000,
        )

        num_dx = self._rng.randint(1, 5)
        dx_samples = self._rng.sample(
            self.COMMON_DIAGNOSES, min(num_dx, len(self.COMMON_DIAGNOSES))
        )
        diagnoses = [
            Diagnosis(
                icd10_code=code,
                description=desc,
                date_diagnosed=str(date.today() - timedelta(days=self._rng.randint(30, 1825))),
            )
            for code, desc in dx_samples
        ]

        num_meds = self._rng.randint(0, 4)
        med_samples = self._rng.sample(
            self.COMMON_MEDICATIONS, min(num_meds, len(self.COMMON_MEDICATIONS))
        )
        medications = [
            Medication(
                name=name,
                dosage=dose,
                frequency=freq,
                start_date=str(date.today() - timedelta(days=self._rng.randint(30, 365))),
                prescriber=f"Dr. {self._rng.choice(self.LAST_NAMES)}",
            )
            for name, dose, freq in med_samples
        ]

        sex = overrides.get("sex", self._rng.choice(["Male", "Female"]))
        patient_data = {
            "patient_id": pid,
            "first_name": self._rng.choice(self.FIRST_NAMES),
            "last_name": self._rng.choice(self.LAST_NAMES),
            "date_of_birth": str(dob),
            "age": age,
            "sex": sex,
            "race": self._rng.choice(
                [
                    "White",
                    "Black",
                    "Asian",
                    "Hispanic",
                    "Native American",
                    "Pacific Islander",
                ]
            ),
            "ethnicity": self._rng.choice(["Hispanic", "Non-Hispanic"]),
            "insurance": insurance,
            "medications": medications,
            "diagnoses": diagnoses,
            "allergies": self._rng.sample(
                ["Penicillin", "Sulfa", "Latex", "Iodine", "NSAIDs", "None"],
                k=self._rng.randint(0, 2),
            ),
            "vitals": {
                "bp_systolic": self._rng.randint(100, 180),
                "bp_diastolic": self._rng.randint(60, 110),
                "heart_rate": self._rng.randint(55, 110),
                "temperature": round(self._rng.uniform(97.0, 101.5), 1),
                "weight_lbs": self._rng.randint(100, 300),
                "height_in": self._rng.randint(58, 76),
            },
        }
        patient_data.update(overrides)
        return Patient.model_validate(patient_data)

    def generate_cohort(self, size: int = 100) -> list[Patient]:
        """Generate a cohort of synthetic patients."""
        return [self.generate(patient_id=f"P{i:05d}") for i in range(size)]
