"""Base agent adapter and execution types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    TOOL_CALL = "tool_call"
    DECISION = "decision"
    ESCALATION = "escalation"
    RESPONSE = "response"


class AgentAction(BaseModel):
    """A single action taken by an agent during scenario execution."""

    action_type: ActionType
    tool_name: str | None = None
    tool_args: dict[str, Any] = Field(default_factory=dict)
    output: Any = None
    reasoning: str = ""
    confidence: float | None = None
    timestamp_ms: float = 0.0


class AgentResponse(BaseModel):
    """Complete response from an agent for a scenario."""

    scenario_id: str
    agent_name: str
    actions: list[AgentAction] = Field(default_factory=list)
    final_answer: dict[str, Any] = Field(default_factory=dict)
    escalated: bool = False
    escalation_reason: str = ""
    total_tokens: int = 0
    total_time_ms: float = 0.0
    error: str | None = None


class AgentAdapter(ABC):
    """Abstract base class for agent adapters.

    Implement this to plug any agent framework (LangChain, LangGraph,
    CrewAI, custom) into ClinicalAgent-Bench.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this agent."""

    @abstractmethod
    async def run_scenario(
        self,
        patient_context: str,
        available_tools: list[str],
        tool_descriptions: dict[str, str],
        additional_context: dict[str, Any],
    ) -> AgentResponse:
        """Run the agent through a single scenario.

        Args:
            patient_context: The clinical context string from the scenario.
            available_tools: Names of tools the agent can call.
            tool_descriptions: Human-readable descriptions of each tool.
            additional_context: Domain-specific context (payer, prior notes, etc).

        Returns:
            AgentResponse with all actions taken and final answer.
        """

    async def setup(self) -> None:
        """Optional setup before running scenarios (e.g., API key validation)."""

    async def teardown(self) -> None:
        """Optional cleanup after running scenarios."""
