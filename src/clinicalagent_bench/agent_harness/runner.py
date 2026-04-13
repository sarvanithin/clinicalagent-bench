"""Benchmark runner that executes agents through scenarios with state tracking."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from pydantic import BaseModel, Field

from clinicalagent_bench.agent_harness.base import AgentAdapter, AgentResponse
from clinicalagent_bench.scenario_engine.models import Scenario
from clinicalagent_bench.virtual_env.tools import ToolRegistry


TOOL_DESCRIPTIONS: dict[str, str] = {
    "ehr_query": "Query patient EHR data (demographics, diagnoses, medications, encounters, vitals, insurance)",
    "ehr_write": "Write to patient EHR (encounter, diagnosis, prescription)",
    "cpt_lookup": "Look up CPT procedure codes by keyword or code",
    "icd10_search": "Search ICD-10 diagnosis codes by keyword or code",
    "claim_submit": "Submit a claim with codes for payer validation",
    "claim_status": "Check the status of a submitted claim",
    "payer_rules": "Get payer-specific rules for auth and claims",
    "prior_auth_submit": "Submit a prior authorization request",
    "prior_auth_status": "Check prior authorization status",
    "lab_order": "Order laboratory tests",
    "lab_results": "Retrieve lab results",
    "pharmacy_check": "Check drug interactions and coverage",
    "prescription_write": "Write a prescription",
    "scheduling_query": "Query available appointment slots",
    "scheduling_book": "Book an appointment",
    "referral_submit": "Submit a patient referral",
    "provider_search": "Search for providers by specialty/location",
    "patient_history": "Get comprehensive patient history",
    "insurance_verify": "Verify patient insurance eligibility",
    "documentation_generate": "Generate clinical documentation from template",
    "escalate_to_human": "Escalate to human reviewer with reason",
}


class RunConfig(BaseModel):
    """Configuration for a benchmark run."""

    timeout_seconds: float = Field(default=120.0, description="Max time per scenario")
    max_tool_calls: int = Field(default=50, description="Max tool calls per scenario")
    parallel_scenarios: int = Field(default=1, description="Number of scenarios to run in parallel")
    consistency_runs: int = Field(default=1, description="Number of times to run each scenario for consistency scoring")
    seed: int = Field(default=42)


class ScenarioRun(BaseModel):
    """Result of running a single scenario."""

    scenario_id: str
    scenario_name: str
    domain: str
    difficulty: str
    risk_level: str
    response: AgentResponse
    tool_calls_made: list[dict[str, Any]] = Field(default_factory=list)
    state_snapshots: list[dict[str, Any]] = Field(default_factory=list)
    timed_out: bool = False


class BenchmarkResult(BaseModel):
    """Complete result of a benchmark run."""

    agent_name: str
    run_id: str
    config: RunConfig
    scenario_runs: list[ScenarioRun] = Field(default_factory=list)
    total_scenarios: int = 0
    completed_scenarios: int = 0
    failed_scenarios: int = 0
    total_time_ms: float = 0.0


class BenchmarkRunner:
    """Runs agents through clinical benchmark scenarios."""

    def __init__(self, config: RunConfig | None = None) -> None:
        self.config = config or RunConfig()

    async def run_scenario(
        self,
        agent: AgentAdapter,
        scenario: Scenario,
        tool_registry: ToolRegistry | None = None,
    ) -> ScenarioRun:
        """Run a single scenario with an agent."""
        tools = tool_registry or ToolRegistry()
        tools.reset()

        available = [t.value for t in scenario.input.available_tools]
        descriptions = {t: TOOL_DESCRIPTIONS.get(t, "") for t in available}
        additional = dict(scenario.input.additional_context)
        if scenario.input.payer:
            additional["payer"] = scenario.input.payer.value

        start = time.monotonic()
        timed_out = False

        try:
            response = await asyncio.wait_for(
                agent.run_scenario(
                    patient_context=scenario.input.patient_context,
                    available_tools=available,
                    tool_descriptions=descriptions,
                    additional_context=additional,
                ),
                timeout=self.config.timeout_seconds,
            )
        except asyncio.TimeoutError:
            timed_out = True
            elapsed = (time.monotonic() - start) * 1000
            response = AgentResponse(
                scenario_id=scenario.scenario_id,
                agent_name=agent.name,
                total_time_ms=elapsed,
                error="Scenario timed out",
            )

        return ScenarioRun(
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.name,
            domain=scenario.domain.value,
            difficulty=scenario.difficulty.value,
            risk_level=scenario.risk_level.value,
            response=response,
            tool_calls_made=tools.call_log,
            timed_out=timed_out,
        )

    async def run_benchmark(
        self,
        agent: AgentAdapter,
        scenarios: list[Scenario],
        tool_registry: ToolRegistry | None = None,
    ) -> BenchmarkResult:
        """Run a full benchmark suite against an agent."""
        run_id = f"{agent.name}-{int(time.time())}"
        result = BenchmarkResult(
            agent_name=agent.name,
            run_id=run_id,
            config=self.config,
            total_scenarios=len(scenarios),
        )

        start = time.monotonic()
        await agent.setup()

        try:
            if self.config.parallel_scenarios > 1:
                semaphore = asyncio.Semaphore(self.config.parallel_scenarios)

                async def _run_with_sem(s: Scenario) -> ScenarioRun:
                    async with semaphore:
                        return await self.run_scenario(agent, s, tool_registry)

                runs = await asyncio.gather(
                    *[_run_with_sem(s) for s in scenarios],
                    return_exceptions=True,
                )
                for run in runs:
                    if isinstance(run, Exception):
                        result.failed_scenarios += 1
                    else:
                        result.scenario_runs.append(run)
                        if run.response.error:
                            result.failed_scenarios += 1
                        else:
                            result.completed_scenarios += 1
            else:
                for scenario in scenarios:
                    run = await self.run_scenario(agent, scenario, tool_registry)
                    result.scenario_runs.append(run)
                    if run.response.error:
                        result.failed_scenarios += 1
                    else:
                        result.completed_scenarios += 1
        finally:
            await agent.teardown()

        result.total_time_ms = (time.monotonic() - start) * 1000
        return result
