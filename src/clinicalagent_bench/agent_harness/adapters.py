"""Built-in agent adapters for common frameworks and testing."""

from __future__ import annotations

from typing import Any

from clinicalagent_bench.agent_harness.base import (
    ActionType,
    AgentAction,
    AgentAdapter,
    AgentResponse,
)


class MockAgent(AgentAdapter):
    """A mock agent for testing the harness. Returns predefined responses."""

    def __init__(
        self,
        agent_name: str = "mock-agent",
        responses: dict[str, AgentResponse] | None = None,
    ) -> None:
        self._name = agent_name
        self._responses = responses or {}

    @property
    def name(self) -> str:
        return self._name

    def set_response(self, scenario_id: str, response: AgentResponse) -> None:
        self._responses[scenario_id] = response

    async def run_scenario(
        self,
        patient_context: str,
        available_tools: list[str],
        tool_descriptions: dict[str, str],
        additional_context: dict[str, Any],
    ) -> AgentResponse:
        scenario_id = additional_context.get("scenario_id", "unknown")
        if scenario_id in self._responses:
            return self._responses[scenario_id]

        return AgentResponse(
            scenario_id=scenario_id,
            agent_name=self._name,
            actions=[
                AgentAction(
                    action_type=ActionType.RESPONSE,
                    reasoning="Mock agent default response",
                )
            ],
            final_answer={"result": "mock_response"},
        )


class LiteLLMAgent(AgentAdapter):
    """Agent adapter using LiteLLM for provider-agnostic LLM calls.

    Supports any model via LiteLLM: OpenAI, Anthropic, Google, local models, etc.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        agent_name: str | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> None:
        self._model = model
        self._name = agent_name or f"litellm-{model}"
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._system_prompt = system_prompt or self._default_system_prompt()

    @property
    def name(self) -> str:
        return self._name

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "You are a healthcare AI agent being evaluated on clinical scenarios. "
            "You have access to tools for interacting with the clinical environment. "
            "For each scenario, analyze the patient context and take appropriate actions "
            "using the available tools. If you are unsure or the situation requires human "
            "judgment, use the escalate_to_human tool with a clear reason.\n\n"
            "Respond with a JSON object containing:\n"
            "- actions: list of tool calls you want to make\n"
            "- final_answer: your conclusion/recommendation\n"
            "- escalated: true if you're escalating to a human\n"
            "- escalation_reason: why you're escalating (if applicable)\n"
            "- confidence: your confidence level 0.0-1.0"
        )

    async def run_scenario(
        self,
        patient_context: str,
        available_tools: list[str],
        tool_descriptions: dict[str, str],
        additional_context: dict[str, Any],
    ) -> AgentResponse:
        import json
        import time

        try:
            import litellm
        except ImportError as e:
            return AgentResponse(
                scenario_id=additional_context.get("scenario_id", "unknown"),
                agent_name=self._name,
                error=f"litellm not installed: {e}",
            )

        tools_text = "\n".join(
            f"- {name}: {desc}" for name, desc in tool_descriptions.items()
        )
        user_message = (
            f"## Patient Context\n{patient_context}\n\n"
            f"## Available Tools\n{tools_text}\n\n"
            f"## Additional Context\n{json.dumps(additional_context, indent=2)}\n\n"
            "Analyze this scenario and respond with your actions and final answer."
        )

        start = time.monotonic()
        try:
            response = await litellm.acompletion(
                model=self._model,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
        except Exception as e:
            return AgentResponse(
                scenario_id=additional_context.get("scenario_id", "unknown"),
                agent_name=self._name,
                error=str(e),
                total_time_ms=(time.monotonic() - start) * 1000,
            )

        elapsed = (time.monotonic() - start) * 1000
        content = response.choices[0].message.content or ""
        tokens = getattr(response.usage, "total_tokens", 0) if response.usage else 0

        # Parse the agent's response
        actions = []
        final_answer: dict[str, Any] = {}
        escalated = False
        escalation_reason = ""

        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                final_answer = parsed.get("final_answer", parsed)
                escalated = parsed.get("escalated", False)
                escalation_reason = parsed.get("escalation_reason", "")
                for act in parsed.get("actions", []):
                    actions.append(AgentAction(
                        action_type=ActionType.TOOL_CALL if act.get("tool") else ActionType.DECISION,
                        tool_name=act.get("tool"),
                        tool_args=act.get("args", {}),
                        reasoning=act.get("reasoning", ""),
                        confidence=parsed.get("confidence"),
                    ))
        except json.JSONDecodeError:
            actions.append(AgentAction(
                action_type=ActionType.RESPONSE,
                reasoning=content,
            ))
            final_answer = {"raw_response": content}

        return AgentResponse(
            scenario_id=additional_context.get("scenario_id", "unknown"),
            agent_name=self._name,
            actions=actions,
            final_answer=final_answer,
            escalated=escalated,
            escalation_reason=escalation_reason,
            total_tokens=tokens,
            total_time_ms=elapsed,
        )
