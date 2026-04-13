"""FastAPI server for ClinicalAgent-Bench leaderboard and results API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from clinicalagent_bench.api.db import BenchmarkDB
from clinicalagent_bench.scenario_engine.loader import ScenarioLoader
from clinicalagent_bench.scenario_engine.registry import ScenarioRegistry

app = FastAPI(
    title="ClinicalAgent-Bench",
    description="Evaluation framework for healthcare AI agents",
    version="0.1.0",
)

db = BenchmarkDB()
DEFAULT_SCENARIOS = Path(__file__).parent.parent.parent.parent / "scenarios"


class SubmitRequest(BaseModel):
    """Request body for submitting benchmark results."""

    agent_name: str
    run_id: str
    model: str = ""
    overall_cas: float = Field(ge=0.0, le=1.0)
    total_scenarios: int
    scored_scenarios: int
    scenario_scores: list[dict[str, Any]] = Field(default_factory=list)
    domain_breakdown: dict[str, float] = Field(default_factory=dict)
    safety_summary: dict[str, Any] = Field(default_factory=dict)
    refusal_summary: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)


class LeaderboardEntry(BaseModel):
    rank: int
    agent_name: str
    model: str
    overall_cas: float
    total_scenarios: int
    domain_breakdown: dict[str, float]
    safety_violation_rate: float
    refusal_f1: float
    created_at: str


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "ClinicalAgent-Bench",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/api/v1/leaderboard")
async def get_leaderboard(limit: int = 50) -> list[LeaderboardEntry]:
    """Get the leaderboard of top-performing agents."""
    entries = db.get_leaderboard(limit=limit)
    return [
        LeaderboardEntry(
            rank=i + 1,
            agent_name=e["agent_name"],
            model=e.get("model", ""),
            overall_cas=e["overall_cas"],
            total_scenarios=e["total_scenarios"],
            domain_breakdown=e.get("domain_breakdown", {}),
            safety_violation_rate=e.get("safety_summary", {}).get("violation_rate", 0.0),
            refusal_f1=e.get("refusal_summary", {}).get("f1", 0.0),
            created_at=e["created_at"],
        )
        for i, e in enumerate(entries)
    ]


@app.post("/api/v1/submit")
async def submit_results(request: SubmitRequest) -> dict[str, str]:
    """Submit benchmark results for an agent."""
    run_id = db.save_benchmark(request.model_dump())
    return {"status": "success", "run_id": run_id}


@app.get("/api/v1/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    """Get detailed results for a specific benchmark run."""
    result = db.get_run(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return result


@app.get("/api/v1/scenarios")
async def list_scenarios(domain: str | None = None) -> list[dict[str, Any]]:
    """List available benchmark scenarios."""
    loader = ScenarioLoader(DEFAULT_SCENARIOS)
    registry = ScenarioRegistry()

    try:
        all_scenarios = loader.load_all()
        for group in all_scenarios.values():
            registry.register_many(group)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    from clinicalagent_bench.scenario_engine.models import Domain
    filters: dict[str, Any] = {}
    if domain:
        filters["domain"] = Domain(domain)

    scenarios = registry.filter(**filters)
    return [
        {
            "scenario_id": s.scenario_id,
            "name": s.name,
            "domain": s.domain.value,
            "difficulty": s.difficulty.value,
            "risk_level": s.risk_level.value,
            "tags": s.tags,
        }
        for s in scenarios
    ]


@app.get("/api/v1/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str) -> dict[str, Any]:
    """Get detailed information about a specific scenario."""
    loader = ScenarioLoader(DEFAULT_SCENARIOS)
    registry = ScenarioRegistry()

    try:
        all_scenarios = loader.load_all()
        for group in all_scenarios.values():
            registry.register_many(group)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    scenario = registry.get(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")

    return scenario.model_dump()


@app.get("/api/v1/scenarios/{scenario_id}/history")
async def get_scenario_history(scenario_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Get score history for a specific scenario across all runs."""
    return db.get_scenario_history(scenario_id, limit=limit)


@app.get("/api/v1/compare")
async def compare_runs(run_ids: str) -> dict[str, Any]:
    """Compare multiple benchmark runs side by side.

    Args:
        run_ids: Comma-separated list of run IDs to compare.
    """
    ids = [r.strip() for r in run_ids.split(",")]
    runs = []
    for rid in ids:
        result = db.get_run(rid)
        if result:
            runs.append(result)

    if not runs:
        raise HTTPException(status_code=404, detail="No matching runs found")

    return {
        "runs": runs,
        "comparison": {
            "cas_scores": {r["run_id"]: r["overall_cas"] for r in runs},
            "domain_breakdown": {r["run_id"]: r["domain_breakdown"] for r in runs},
        },
    }


@app.get("/api/v1/stats")
async def get_stats() -> dict[str, Any]:
    """Get overall benchmark statistics."""
    leaderboard = db.get_leaderboard(limit=1000)

    if not leaderboard:
        return {"total_runs": 0, "agents": 0}

    cas_scores = [e["overall_cas"] for e in leaderboard]
    unique_agents = set(e["agent_name"] for e in leaderboard)

    return {
        "total_runs": len(leaderboard),
        "unique_agents": len(unique_agents),
        "average_cas": sum(cas_scores) / len(cas_scores),
        "best_cas": max(cas_scores),
        "worst_cas": min(cas_scores),
    }
