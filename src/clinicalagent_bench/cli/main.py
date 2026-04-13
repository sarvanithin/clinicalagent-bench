"""ClinicalAgent-Bench CLI interface."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from clinicalagent_bench.scenario_engine.loader import ScenarioLoader
from clinicalagent_bench.scenario_engine.models import Difficulty, Domain
from clinicalagent_bench.scenario_engine.registry import ScenarioRegistry

console = Console()

DEFAULT_SCENARIOS_DIR = Path(__file__).parent.parent.parent.parent / "scenarios"


@click.group()
@click.version_option(version="0.1.0", prog_name="ClinicalAgent-Bench")
def cli() -> None:
    """ClinicalAgent-Bench: Evaluation framework for healthcare AI agents."""


@cli.command()
@click.option(
    "--scenarios-dir",
    "-s",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to scenarios directory",
)
@click.option("--domain", "-d", type=click.Choice([d.value for d in Domain]), default=None)
@click.option("--difficulty", type=click.Choice([d.value for d in Difficulty]), default=None)
@click.option("--verbose", "-v", is_flag=True)
def list(
    scenarios_dir: Path | None, domain: str | None, difficulty: str | None, verbose: bool
) -> None:
    """List available benchmark scenarios."""
    scenarios_dir = scenarios_dir or DEFAULT_SCENARIOS_DIR
    loader = ScenarioLoader(scenarios_dir)
    registry = ScenarioRegistry()

    try:
        all_scenarios = loader.load_all()
        for group in all_scenarios.values():
            registry.register_many(group)
    except Exception as e:
        console.print(f"[red]Error loading scenarios: {e}[/red]")
        raise SystemExit(1)

    filters = {}
    if domain:
        filters["domain"] = Domain(domain)
    if difficulty:
        filters["difficulty"] = Difficulty(difficulty)

    scenarios = registry.filter(**filters)

    if not scenarios:
        console.print("[yellow]No scenarios found matching filters.[/yellow]")
        return

    table = Table(title=f"ClinicalAgent-Bench Scenarios ({len(scenarios)} total)")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Domain", style="green")
    table.add_column("Difficulty", style="yellow")
    table.add_column("Risk", style="red")

    for s in scenarios:
        table.add_row(
            s.scenario_id,
            s.name,
            s.domain.value,
            s.difficulty.value,
            s.risk_level.value,
        )

    console.print(table)

    if verbose:
        summary = registry.domains_summary()
        console.print("\n[bold]Domain Summary:[/bold]")
        for d, count in sorted(summary.items()):
            console.print(f"  {d}: {count} scenarios")


@cli.command()
@click.option(
    "--scenarios-dir",
    "-s",
    type=click.Path(exists=True, path_type=Path),
    default=None,
)
@click.option("--domain", "-d", type=click.Choice([d.value for d in Domain]), default=None)
@click.option("--difficulty", type=click.Choice([d.value for d in Difficulty]), default=None)
@click.option("--model", "-m", default="gpt-4o", help="LLM model to use via LiteLLM")
@click.option("--parallel", "-p", default=1, type=int, help="Parallel scenario execution")
@click.option("--timeout", "-t", default=120, type=int, help="Timeout per scenario (seconds)")
@click.option(
    "--output", "-o", type=click.Path(path_type=Path), default=None, help="Output file for results"
)
def run(
    scenarios_dir: Path | None,
    domain: str | None,
    difficulty: str | None,
    model: str,
    parallel: int,
    timeout: int,
    output: Path | None,
) -> None:
    """Run benchmark scenarios against an agent."""
    scenarios_dir = scenarios_dir or DEFAULT_SCENARIOS_DIR
    loader = ScenarioLoader(scenarios_dir)
    registry = ScenarioRegistry()

    try:
        all_scenarios = loader.load_all()
        for group in all_scenarios.values():
            registry.register_many(group)
    except Exception as e:
        console.print(f"[red]Error loading scenarios: {e}[/red]")
        raise SystemExit(1)

    filters = {}
    if domain:
        filters["domain"] = Domain(domain)
    if difficulty:
        filters["difficulty"] = Difficulty(difficulty)

    scenarios = registry.filter(**filters)

    if not scenarios:
        console.print("[yellow]No scenarios found matching filters.[/yellow]")
        return

    console.print(
        Panel(
            f"Running [bold]{len(scenarios)}[/bold] scenarios against [cyan]{model}[/cyan]\n"
            f"Parallel: {parallel} | Timeout: {timeout}s",
            title="ClinicalAgent-Bench",
        )
    )

    from clinicalagent_bench.agent_harness.adapters import LiteLLMAgent
    from clinicalagent_bench.agent_harness.runner import BenchmarkRunner, RunConfig
    from clinicalagent_bench.scoring_engine.scorer import Scorer

    agent = LiteLLMAgent(model=model)
    config = RunConfig(
        timeout_seconds=timeout,
        parallel_scenarios=parallel,
    )
    runner = BenchmarkRunner(config)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running benchmark...", total=None)
        result = asyncio.run(runner.run_benchmark(agent, scenarios))
        progress.update(task, completed=True)

    # Score results
    scenario_map = {s.scenario_id: s for s in scenarios}
    scorer = Scorer()
    scores = scorer.score_benchmark(result, scenario_map)

    # Display results
    _display_results(scores)

    # Save if output specified
    if output:
        output.write_text(scores.model_dump_json(indent=2))
        console.print(f"\n[green]Results saved to {output}[/green]")


@cli.command()
@click.argument("results_file", type=click.Path(exists=True, path_type=Path))
def score(results_file: Path) -> None:
    """Display scores from a results file."""
    from clinicalagent_bench.scoring_engine.scorer import BenchmarkScores

    data = json.loads(results_file.read_text())
    scores = BenchmarkScores.model_validate(data)
    _display_results(scores)


@cli.command()
@click.option(
    "--scenarios-dir",
    "-s",
    type=click.Path(exists=True, path_type=Path),
    default=None,
)
def validate(scenarios_dir: Path | None) -> None:
    """Validate all scenario YAML files for correctness."""
    scenarios_dir = scenarios_dir or DEFAULT_SCENARIOS_DIR
    loader = ScenarioLoader(scenarios_dir)

    console.print(f"Validating scenarios in [cyan]{scenarios_dir}[/cyan]...")

    try:
        all_scenarios = loader.load_all()
        total = sum(len(v) for v in all_scenarios.values())
        console.print(
            f"[green]All {total} scenarios valid across {len(all_scenarios)} domains.[/green]"
        )

        table = Table(title="Scenario Validation Summary")
        table.add_column("Domain", style="cyan")
        table.add_column("Count", style="green", justify="right")

        for domain, scenarios in sorted(all_scenarios.items()):
            table.add_row(domain, str(len(scenarios)))

        console.print(table)

    except Exception as e:
        console.print(f"[red]Validation failed: {e}[/red]")
        raise SystemExit(1)


@cli.command()
@click.argument("scenario_id")
@click.option(
    "--scenarios-dir",
    "-s",
    type=click.Path(exists=True, path_type=Path),
    default=None,
)
def inspect(scenario_id: str, scenarios_dir: Path | None) -> None:
    """Inspect a specific scenario in detail."""
    scenarios_dir = scenarios_dir or DEFAULT_SCENARIOS_DIR
    loader = ScenarioLoader(scenarios_dir)
    registry = ScenarioRegistry()

    try:
        all_scenarios = loader.load_all()
        for group in all_scenarios.values():
            registry.register_many(group)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    scenario = registry.get(scenario_id)
    if not scenario:
        console.print(f"[red]Scenario '{scenario_id}' not found.[/red]")
        raise SystemExit(1)

    console.print(
        Panel(
            f"[bold]{scenario.name}[/bold]\n\n"
            f"{scenario.description}\n\n"
            f"Domain: [green]{scenario.domain.value}[/green] | "
            f"Difficulty: [yellow]{scenario.difficulty.value}[/yellow] | "
            f"Risk: [red]{scenario.risk_level.value}[/red]\n"
            f"Tags: {', '.join(scenario.tags)}",
            title=f"Scenario: {scenario.scenario_id}",
        )
    )

    console.print("\n[bold]Patient Context:[/bold]")
    console.print(f"  {scenario.input.patient_context}")

    console.print(
        f"\n[bold]Available Tools:[/bold] {', '.join(t.value for t in scenario.input.available_tools)}"
    )

    console.print(f"\n[bold]Expected Actions ({len(scenario.expected_actions)}):[/bold]")
    for action in scenario.expected_actions:
        required = "[red]*[/red]" if action.required else " "
        console.print(f"  {required} Step {action.step}: {action.action}")

    if scenario.safety_constraints:
        console.print(f"\n[bold]Safety Constraints ({len(scenario.safety_constraints)}):[/bold]")
        for c in scenario.safety_constraints:
            console.print(f"  [{c.severity}] {c.constraint}")

    if scenario.escalation_triggers:
        console.print(f"\n[bold]Escalation Triggers ({len(scenario.escalation_triggers)}):[/bold]")
        for t in scenario.escalation_triggers:
            hidden = " (hidden)" if t.is_hidden else ""
            console.print(f"  {t.condition}{hidden} → {t.expected_action}")

    if scenario.edge_cases:
        console.print(f"\n[bold]Edge Cases ({len(scenario.edge_cases)}):[/bold]")
        for e in scenario.edge_cases:
            console.print(f"  - {e.description}")


@cli.command()
@click.argument("results_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output", "-o", type=click.Path(path_type=Path), default=None, help="Output JSON file"
)
@click.option("--markdown", is_flag=True, help="Print Markdown report to stdout")
@click.option("--agent-name", default="", help="Agent name for the report")
@click.option("--model", "-m", default="", help="Model name for the report")
def compliance(
    results_file: Path,
    output: Path | None,
    markdown: bool,
    agent_name: str,
    model: str,
) -> None:
    """Generate FDA GMLP compliance report from benchmark results."""
    from clinicalagent_bench.scoring_engine.compliance import GMLPComplianceReporter
    from clinicalagent_bench.scoring_engine.scorer import BenchmarkScores

    data = json.loads(results_file.read_text())
    scores = BenchmarkScores.model_validate(data)

    reporter = GMLPComplianceReporter()
    report = reporter.generate(
        scores,
        agent_name=agent_name or scores.agent_name,
        model=model,
    )

    # Display summary
    color = (
        "green"
        if report.overall_compliance >= 0.7
        else "yellow"
        if report.overall_compliance >= 0.5
        else "red"
    )
    console.print(
        Panel(
            f"[bold {color}]GMLP Compliance: {report.overall_compliance:.0%}[/bold {color}]\n\n"
            f"Agent: [cyan]{report.agent_name}[/cyan]\n"
            f"CAS: {report.cas_score:.3f} | Safety: {report.safety_score:.3f}\n"
            f"Critical Violations: {report.critical_violations}",
            title="FDA GMLP Compliance Report",
        )
    )

    # Principle table
    table = Table(title="GMLP Principle Assessment")
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Principle", style="white", max_width=50)
    table.add_column("Status", justify="center")
    table.add_column("Score", justify="right")

    status_styles = {
        "compliant": "[green]PASS[/green]",
        "partial": "[yellow]PARTIAL[/yellow]",
        "non_compliant": "[red]FAIL[/red]",
        "not_applicable": "[dim]N/A[/dim]",
    }

    for a in report.principle_assessments:
        table.add_row(
            str(a.principle_number),
            a.principle_title[:50],
            status_styles.get(a.status, a.status),
            f"{a.score:.2f}",
        )

    console.print(table)

    if report.regulatory_notes:
        console.print("\n[bold]Regulatory Notes:[/bold]")
        for note in report.regulatory_notes:
            console.print(f"  [yellow]- {note}[/yellow]")

    if markdown:
        md = reporter.export_markdown(report)
        console.print(f"\n{md}")

    if output:
        reporter.export_json(report, str(output))
        console.print(f"\n[green]Report saved to {output}[/green]")


def _display_results(scores: object) -> None:
    """Display benchmark scores in a rich table."""
    from clinicalagent_bench.scoring_engine.scorer import BenchmarkScores

    if not isinstance(scores, BenchmarkScores):
        return

    # Overall score
    cas = scores.overall_cas
    color = "green" if cas >= 0.7 else "yellow" if cas >= 0.5 else "red"
    console.print(
        Panel(
            f"[bold {color}]ClinicalAgent Score (CAS): {cas:.3f}[/bold {color}]\n\n"
            f"Agent: [cyan]{scores.agent_name}[/cyan]\n"
            f"Scenarios: {scores.scored_scenarios}/{scores.total_scenarios}",
            title="Benchmark Results",
        )
    )

    # Domain breakdown
    if scores.domain_breakdown:
        table = Table(title="Domain Breakdown")
        table.add_column("Domain", style="cyan")
        table.add_column("CAS Score", justify="right")

        for domain, score_val in sorted(scores.domain_breakdown.items()):
            color = "green" if score_val >= 0.7 else "yellow" if score_val >= 0.5 else "red"
            table.add_row(domain, f"[{color}]{score_val:.3f}[/{color}]")

        console.print(table)

    # Safety summary
    safety = scores.safety_summary
    if safety:
        console.print(
            f"\n[bold]Safety:[/bold] {safety.get('total_violations', 0)} violations "
            f"/ {safety.get('total_constraints', 0)} constraints "
            f"(rate: {safety.get('violation_rate', 0):.1%})"
        )
        critical = safety.get("critical_violations", 0)
        if critical > 0:
            console.print(f"  [red]Critical violations: {critical}[/red]")

    # Refusal summary
    refusal = scores.refusal_summary
    if refusal:
        console.print(
            f"\n[bold]Refusal Accuracy:[/bold] "
            f"Precision={refusal.get('precision', 0):.3f} "
            f"Recall={refusal.get('recall', 0):.3f} "
            f"F1={refusal.get('f1', 0):.3f}"
        )


if __name__ == "__main__":
    cli()
