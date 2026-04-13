"""Stress testing framework for multi-agent coordination scenarios.

Runs scenarios under adverse conditions — concurrent execution, message
delays, partial failures — to evaluate agent resilience and coordination
quality under pressure.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from clinicalagent_bench.agent_harness.base import AgentAdapter, AgentResponse
from clinicalagent_bench.scenario_engine.models import Scenario


@dataclass
class StressConfig:
    """Configuration for stress test execution."""

    concurrent_scenarios: int = 5
    timeout_seconds: float = 120.0
    inject_delays: bool = False
    delay_range_ms: tuple[int, int] = (100, 2000)
    inject_failures: bool = False
    failure_rate: float = 0.1
    repeat_count: int = 3
    max_retries: int = 2


@dataclass
class StressResult:
    """Result of a single stress test scenario execution."""

    scenario_id: str
    iteration: int
    success: bool
    response: AgentResponse | None = None
    error: str = ""
    latency_ms: float = 0.0
    retries: int = 0


@dataclass
class StressReport:
    """Aggregated stress test report."""

    total_executions: int = 0
    successful: int = 0
    failed: int = 0
    timed_out: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    consistency_score: float = 0.0
    results: list[StressResult] = field(default_factory=list)
    degradation_detected: bool = False
    summary: str = ""


class StressTestRunner:
    """Run multi-agent scenarios under stress conditions.

    Evaluates:
    - Concurrent execution stability
    - Response consistency across repeated runs
    - Graceful degradation under load
    - Timeout handling and retry behavior
    - Output determinism under parallel pressure

    Usage:
        runner = StressTestRunner(agent, config=StressConfig(concurrent_scenarios=10))
        report = await runner.run(scenarios)
    """

    def __init__(self, agent: AgentAdapter, config: StressConfig | None = None) -> None:
        self._agent = agent
        self._config = config or StressConfig()

    async def run(self, scenarios: list[Scenario]) -> StressReport:
        """Execute stress test across all scenarios.

        Args:
            scenarios: Scenarios to stress test (typically multi_agent domain).

        Returns:
            StressReport with latency, consistency, and failure metrics.
        """
        results: list[StressResult] = []

        for iteration in range(self._config.repeat_count):
            semaphore = asyncio.Semaphore(self._config.concurrent_scenarios)
            tasks = [
                self._run_with_semaphore(semaphore, scenario, iteration) for scenario in scenarios
            ]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)

        return self._compile_report(results, scenarios)

    async def _run_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        scenario: Scenario,
        iteration: int,
    ) -> StressResult:
        """Run a single scenario with concurrency control."""
        async with semaphore:
            return await self._run_scenario(scenario, iteration)

    async def _run_scenario(self, scenario: Scenario, iteration: int) -> StressResult:
        """Execute a single scenario with timeout, retry, and optional fault injection."""
        retries = 0

        while retries <= self._config.max_retries:
            start = time.monotonic()
            try:
                if self._config.inject_delays:
                    delay = (
                        self._config.delay_range_ms[0]
                        + (
                            hash(f"{scenario.scenario_id}-{iteration}-{retries}")
                            % (self._config.delay_range_ms[1] - self._config.delay_range_ms[0])
                        )
                    ) / 1000.0
                    await asyncio.sleep(delay)

                if self._config.inject_failures:
                    fail_hash = hash(f"fail-{scenario.scenario_id}-{iteration}-{retries}")
                    if (fail_hash % 100) / 100.0 < self._config.failure_rate:
                        raise RuntimeError("Injected fault")

                response = await asyncio.wait_for(
                    self._agent.run_scenario(
                        patient_context=scenario.input.patient_context,
                        available_tools=[t.value for t in scenario.input.available_tools],
                        tool_descriptions={},
                        additional_context={
                            "scenario_id": scenario.scenario_id,
                            "stress_iteration": iteration,
                        },
                    ),
                    timeout=self._config.timeout_seconds,
                )

                latency = (time.monotonic() - start) * 1000
                return StressResult(
                    scenario_id=scenario.scenario_id,
                    iteration=iteration,
                    success=True,
                    response=response,
                    latency_ms=latency,
                    retries=retries,
                )

            except TimeoutError:
                latency = (time.monotonic() - start) * 1000
                return StressResult(
                    scenario_id=scenario.scenario_id,
                    iteration=iteration,
                    success=False,
                    error="Timeout",
                    latency_ms=latency,
                    retries=retries,
                )
            except Exception as e:
                retries += 1
                if retries > self._config.max_retries:
                    latency = (time.monotonic() - start) * 1000
                    return StressResult(
                        scenario_id=scenario.scenario_id,
                        iteration=iteration,
                        success=False,
                        error=str(e),
                        latency_ms=latency,
                        retries=retries,
                    )

        latency = (time.monotonic() - start) * 1000
        return StressResult(
            scenario_id=scenario.scenario_id,
            iteration=iteration,
            success=False,
            error="Max retries exceeded",
            latency_ms=latency,
            retries=retries,
        )

    def _compile_report(
        self, results: list[StressResult], scenarios: list[Scenario]
    ) -> StressReport:
        """Compile individual results into an aggregated report."""
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success and r.error != "Timeout")
        timed_out = sum(1 for r in results if r.error == "Timeout")

        latencies = sorted(r.latency_ms for r in results if r.success)
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        p95_latency = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
        p99_latency = latencies[int(len(latencies) * 0.99)] if latencies else 0.0

        # Consistency: compare responses across iterations for same scenario
        consistency = self._compute_consistency(results, scenarios)

        # Degradation: check if later iterations perform worse
        degradation = self._check_degradation(results)

        summary = (
            f"{successful}/{total} successful "
            f"({failed} failed, {timed_out} timed out). "
            f"Avg latency: {avg_latency:.0f}ms, "
            f"P95: {p95_latency:.0f}ms, P99: {p99_latency:.0f}ms. "
            f"Consistency: {consistency:.2f}. "
            f"{'Degradation detected!' if degradation else 'No degradation.'}"
        )

        return StressReport(
            total_executions=total,
            successful=successful,
            failed=failed,
            timed_out=timed_out,
            avg_latency_ms=avg_latency,
            p95_latency_ms=p95_latency,
            p99_latency_ms=p99_latency,
            consistency_score=consistency,
            results=results,
            degradation_detected=degradation,
            summary=summary,
        )

    def _compute_consistency(self, results: list[StressResult], scenarios: list[Scenario]) -> float:
        """Compute consistency score by comparing outputs across iterations."""
        if not scenarios:
            return 1.0

        consistencies = []
        for scenario in scenarios:
            scenario_results = [
                r
                for r in results
                if r.scenario_id == scenario.scenario_id and r.success and r.response
            ]
            if len(scenario_results) < 2:
                continue

            # Compare escalation decisions
            escalation_decisions = [r.response.escalated for r in scenario_results]
            esc_consistency = escalation_decisions.count(escalation_decisions[0]) / len(
                escalation_decisions
            )

            # Compare action counts
            action_counts = [len(r.response.actions) for r in scenario_results]
            if max(action_counts) > 0:
                count_consistency = min(action_counts) / max(action_counts)
            else:
                count_consistency = 1.0

            consistencies.append((esc_consistency + count_consistency) / 2)

        return sum(consistencies) / len(consistencies) if consistencies else 1.0

    def _check_degradation(self, results: list[StressResult]) -> bool:
        """Check if performance degrades across iterations."""
        if len(results) < 6:
            return False

        iterations = sorted(set(r.iteration for r in results))
        if len(iterations) < 2:
            return False

        first_iter = [r for r in results if r.iteration == iterations[0]]
        last_iter = [r for r in results if r.iteration == iterations[-1]]

        first_success = (
            sum(1 for r in first_iter if r.success) / len(first_iter) if first_iter else 1
        )
        last_success = sum(1 for r in last_iter if r.success) / len(last_iter) if last_iter else 1

        return last_success < first_success * 0.8
