"""Scenario registry for indexing, filtering, and retrieving scenarios."""

from __future__ import annotations

from clinicalagent_bench.scenario_engine.models import (
    Difficulty,
    Domain,
    RiskLevel,
    Scenario,
)


class ScenarioRegistry:
    """In-memory registry for fast scenario lookup and filtering."""

    def __init__(self) -> None:
        self._scenarios: dict[str, Scenario] = {}
        self._by_domain: dict[Domain, list[str]] = {}
        self._by_difficulty: dict[Difficulty, list[str]] = {}
        self._by_risk: dict[RiskLevel, list[str]] = {}
        self._by_tag: dict[str, list[str]] = {}

    @property
    def count(self) -> int:
        return len(self._scenarios)

    def register(self, scenario: Scenario) -> None:
        """Add a scenario to the registry."""
        sid = scenario.scenario_id
        self._scenarios[sid] = scenario

        self._by_domain.setdefault(scenario.domain, []).append(sid)
        self._by_difficulty.setdefault(scenario.difficulty, []).append(sid)
        self._by_risk.setdefault(scenario.risk_level, []).append(sid)
        for tag in scenario.tags:
            self._by_tag.setdefault(tag, []).append(sid)

    def register_many(self, scenarios: list[Scenario]) -> None:
        """Add multiple scenarios to the registry."""
        for s in scenarios:
            self.register(s)

    def get(self, scenario_id: str) -> Scenario | None:
        """Get a scenario by ID."""
        return self._scenarios.get(scenario_id)

    def list_ids(self) -> list[str]:
        """List all scenario IDs."""
        return sorted(self._scenarios.keys())

    def filter(
        self,
        domain: Domain | None = None,
        difficulty: Difficulty | None = None,
        risk_level: RiskLevel | None = None,
        tags: list[str] | None = None,
    ) -> list[Scenario]:
        """Filter scenarios by criteria. All criteria are ANDed together."""
        candidate_ids: set[str] | None = None

        if domain is not None:
            ids = set(self._by_domain.get(domain, []))
            candidate_ids = ids if candidate_ids is None else candidate_ids & ids

        if difficulty is not None:
            ids = set(self._by_difficulty.get(difficulty, []))
            candidate_ids = ids if candidate_ids is None else candidate_ids & ids

        if risk_level is not None:
            ids = set(self._by_risk.get(risk_level, []))
            candidate_ids = ids if candidate_ids is None else candidate_ids & ids

        if tags:
            for tag in tags:
                ids = set(self._by_tag.get(tag, []))
                candidate_ids = ids if candidate_ids is None else candidate_ids & ids

        if candidate_ids is None:
            return sorted(self._scenarios.values(), key=lambda s: s.scenario_id)

        return sorted(
            (self._scenarios[sid] for sid in candidate_ids),
            key=lambda s: s.scenario_id,
        )

    def domains_summary(self) -> dict[str, int]:
        """Get count of scenarios per domain."""
        return {d.value: len(ids) for d, ids in self._by_domain.items()}
