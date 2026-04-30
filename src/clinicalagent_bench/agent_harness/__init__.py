"""Agent harness for running healthcare AI agents through benchmark scenarios."""

from clinicalagent_bench.agent_harness.adapters import LiteLLMAgent, MockAgent
from clinicalagent_bench.agent_harness.base import (
    ActionType,
    AgentAction,
    AgentAdapter,
    AgentResponse,
)
from clinicalagent_bench.agent_harness.runner import (
    BenchmarkResult,
    BenchmarkRunner,
    RunConfig,
    ScenarioRun,
)
from clinicalagent_bench.agent_harness.stress import (
    StressConfig,
    StressReport,
    StressResult,
    StressTestRunner,
)


def __getattr__(name: str):  # noqa: ANN001
    """Lazy-load integration adapters so missing deps don't break the package."""
    _INTEGRATION_CLASSES = {
        "LangChainAdapter",
        "CrewAIAdapter",
        "AutoGenAdapter",
        "AnthropicToolUseAdapter",
    }
    if name in _INTEGRATION_CLASSES:
        from clinicalagent_bench.agent_harness import integrations

        return getattr(integrations, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ActionType",
    "AgentAction",
    "AgentAdapter",
    "AgentResponse",
    "AnthropicToolUseAdapter",
    "AutoGenAdapter",
    "BenchmarkResult",
    "BenchmarkRunner",
    "CrewAIAdapter",
    "LangChainAdapter",
    "LiteLLMAgent",
    "MockAgent",
    "RunConfig",
    "ScenarioRun",
    "StressConfig",
    "StressReport",
    "StressResult",
    "StressTestRunner",
]
