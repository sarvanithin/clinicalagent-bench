"""Tests for the FastAPI server."""

import tempfile

import pytest
from fastapi.testclient import TestClient

from clinicalagent_bench.api.db import BenchmarkDB
from clinicalagent_bench.api.server import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = BenchmarkDB(f.name)
        yield db
        db.close()


class TestBenchmarkDB:
    def test_save_and_retrieve(self, temp_db):
        scores_data = {
            "run_id": "test-run-001",
            "agent_name": "test-agent",
            "model": "gpt-4o",
            "overall_cas": 0.75,
            "total_scenarios": 10,
            "scored_scenarios": 10,
            "safety_summary": {"violations": 1},
            "refusal_summary": {"f1": 0.8},
            "domain_breakdown": {"billing_coding": 0.8},
            "scenario_scores": [
                {
                    "scenario_id": "billing-001",
                    "cas_score": 0.75,
                    "safety": {"score": 0.9},
                    "accuracy": {"score": 0.7},
                    "refusal": {"score": 0.8},
                    "efficiency": {"score": 0.6},
                    "consistency": {"score": 1.0},
                },
            ],
        }

        run_id = temp_db.save_benchmark(scores_data)
        assert run_id == "test-run-001"

        result = temp_db.get_run("test-run-001")
        assert result is not None
        assert result["overall_cas"] == 0.75
        assert result["agent_name"] == "test-agent"

    def test_leaderboard(self, temp_db):
        for i in range(5):
            temp_db.save_benchmark(
                {
                    "run_id": f"run-{i}",
                    "agent_name": f"agent-{i}",
                    "overall_cas": 0.5 + i * 0.1,
                    "total_scenarios": 10,
                    "scored_scenarios": 10,
                    "scenario_scores": [],
                }
            )

        leaderboard = temp_db.get_leaderboard(limit=3)
        assert len(leaderboard) == 3
        # Should be sorted by CAS descending
        assert leaderboard[0]["overall_cas"] >= leaderboard[1]["overall_cas"]

    def test_get_nonexistent_run(self, temp_db):
        result = temp_db.get_run("nonexistent")
        assert result is None


class TestAPIEndpoints:
    def test_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "ClinicalAgent-Bench"

    def test_list_scenarios(self, client):
        response = client.get("/api/v1/scenarios")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 35

    def test_list_scenarios_by_domain(self, client):
        response = client.get("/api/v1/scenarios?domain=billing_coding")
        assert response.status_code == 200
        data = response.json()
        assert all(s["domain"] == "billing_coding" for s in data)

    def test_get_scenario(self, client):
        response = client.get("/api/v1/scenarios/billing-001")
        assert response.status_code == 200
        data = response.json()
        assert data["scenario_id"] == "billing-001"

    def test_get_nonexistent_scenario(self, client):
        response = client.get("/api/v1/scenarios/nonexistent-999")
        assert response.status_code == 404

    def test_get_leaderboard_empty(self, client):
        response = client.get("/api/v1/leaderboard")
        assert response.status_code == 200

    def test_get_stats(self, client):
        response = client.get("/api/v1/stats")
        assert response.status_code == 200
