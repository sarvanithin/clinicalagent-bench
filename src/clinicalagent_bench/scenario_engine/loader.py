"""YAML scenario loader with validation."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from clinicalagent_bench.scenario_engine.models import Scenario


class ScenarioLoadError(Exception):
    """Raised when a scenario file cannot be loaded or validated."""

    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"Failed to load {path}: {reason}")


class ScenarioLoader:
    """Loads and validates clinical scenarios from YAML files."""

    def __init__(self, scenarios_dir: Path | str) -> None:
        self.scenarios_dir = Path(scenarios_dir)

    def load_file(self, path: Path | str) -> Scenario:
        """Load a single scenario from a YAML file."""
        path = Path(path)
        if not path.exists():
            raise ScenarioLoadError(path, "File not found")

        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError as e:
            raise ScenarioLoadError(path, f"Invalid YAML: {e}") from e

        if not isinstance(raw, dict):
            raise ScenarioLoadError(path, "Expected a YAML mapping at top level")

        try:
            return Scenario.model_validate(raw)
        except ValidationError as e:
            raise ScenarioLoadError(path, f"Validation error: {e}") from e

    def load_directory(self, domain: str | None = None) -> list[Scenario]:
        """Load all scenarios from the scenarios directory.

        Args:
            domain: If provided, only load scenarios from this subdirectory.
        """
        search_dir = self.scenarios_dir
        if domain:
            search_dir = search_dir / domain

        if not search_dir.exists():
            return []

        scenarios: list[Scenario] = []
        errors: list[ScenarioLoadError] = []

        for yaml_file in sorted(search_dir.rglob("*.yaml")):
            try:
                scenarios.append(self.load_file(yaml_file))
            except ScenarioLoadError as e:
                errors.append(e)

        if errors:
            error_summary = "; ".join(str(e) for e in errors)
            raise ScenarioLoadError(
                search_dir, f"Errors loading {len(errors)} scenarios: {error_summary}"
            )

        return scenarios

    def load_all(self) -> dict[str, list[Scenario]]:
        """Load all scenarios grouped by domain subdirectory."""
        result: dict[str, list[Scenario]] = {}

        if not self.scenarios_dir.exists():
            return result

        for subdir in sorted(self.scenarios_dir.iterdir()):
            if subdir.is_dir() and not subdir.name.startswith("."):
                scenarios = self.load_directory(subdir.name)
                if scenarios:
                    result[subdir.name] = scenarios

        return result
