"""Integration adapters for popular AI agent frameworks.

Each adapter wraps a third-party framework (LangChain, CrewAI, AutoGen,
Anthropic) so that any agent built with those tools can be plugged into
ClinicalAgent-Bench without modification.

All external imports are deferred to method bodies so the package does not
break when a specific framework is not installed.
"""

from __future__ import annotations

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from clinicalagent_bench.agent_harness.base import (
    ActionType,
    AgentAction,
    AgentAdapter,
    AgentResponse,
)
from clinicalagent_bench.scenario_engine.models import ToolName

# Shared thread pool for running sync callables in async context.
_EXECUTOR = ThreadPoolExecutor(max_workers=4)

# ---------------------------------------------------------------------------
# Helper: map free-form tool name strings to our ToolName enum
# ---------------------------------------------------------------------------

_TOOL_NAME_ALIASES: dict[str, ToolName] = {}
for _tn in ToolName:
    _TOOL_NAME_ALIASES[_tn.value] = _tn
    _TOOL_NAME_ALIASES[_tn.value.replace("_", "-")] = _tn
    _TOOL_NAME_ALIASES[_tn.name.lower()] = _tn


def _resolve_tool_name(raw: str | None) -> str | None:
    """Try to map a raw string to a canonical ToolName value."""
    if raw is None:
        return None
    normalized = raw.strip().lower().replace("-", "_")
    tn = _TOOL_NAME_ALIASES.get(normalized)
    return tn.value if tn else raw


def _build_user_message(
    patient_context: str,
    available_tools: list[str],
    tool_descriptions: dict[str, str],
    additional_context: dict[str, Any],
) -> str:
    """Build the standard user prompt from scenario inputs."""
    tools_text = "\n".join(
        f"- {name}: {tool_descriptions.get(name, '')}" for name in available_tools
    )
    return (
        f"## Patient Context\n{patient_context}\n\n"
        f"## Available Tools\n{tools_text}\n\n"
        f"## Additional Context\n{json.dumps(additional_context, indent=2, default=str)}\n\n"
        "Analyze this scenario and respond with your actions and final answer."
    )


# -------------------------------------------------------------------------
# 1. LangChain Adapter
# -------------------------------------------------------------------------


class LangChainAdapter(AgentAdapter):
    """Wraps a LangChain ``AgentExecutor``, ``RunnableSequence``, or any Runnable.

    Usage::

        from langchain.agents import AgentExecutor
        executor = AgentExecutor(agent=..., tools=...)
        adapter = LangChainAdapter(chain=executor, agent_name="my-lc-agent")

    The adapter will:
    * Try ``ainvoke`` first (async), falling back to ``invoke`` in a thread.
    * Extract ``intermediate_steps`` from AgentExecutor output when present.
    * Map LangChain tool names to the ClinicalAgent-Bench ``ToolName`` enum.
    """

    def __init__(
        self,
        chain: Any,
        agent_name: str = "langchain-agent",
        input_key: str = "input",
        output_key: str = "output",
    ) -> None:
        self._chain = chain
        self._name = agent_name
        self._input_key = input_key
        self._output_key = output_key

    @property
    def name(self) -> str:
        return self._name

    async def run_scenario(
        self,
        patient_context: str,
        available_tools: list[str],
        tool_descriptions: dict[str, str],
        additional_context: dict[str, Any],
    ) -> AgentResponse:
        scenario_id = additional_context.get("scenario_id", "unknown")
        prompt = _build_user_message(
            patient_context, available_tools, tool_descriptions, additional_context
        )
        invoke_input: dict[str, Any] | str
        # AgentExecutor expects a dict; plain Runnables may accept a string.
        if hasattr(self._chain, "input_keys"):
            invoke_input = {self._input_key: prompt}
        else:
            invoke_input = prompt

        start = time.monotonic()
        try:
            result = await self._invoke(invoke_input)
        except Exception as e:
            return AgentResponse(
                scenario_id=scenario_id,
                agent_name=self._name,
                error=str(e),
                total_time_ms=(time.monotonic() - start) * 1000,
            )

        elapsed_ms = (time.monotonic() - start) * 1000

        # --- Parse actions from intermediate_steps (AgentExecutor) ---
        actions: list[AgentAction] = []
        intermediate = []
        if isinstance(result, dict):
            intermediate = result.get("intermediate_steps", [])

        for step in intermediate:
            # Each step is (AgentAction, observation)
            try:
                lc_action, observation = step
                tool = _resolve_tool_name(
                    getattr(lc_action, "tool", None)
                )
                tool_input = getattr(lc_action, "tool_input", {})
                if isinstance(tool_input, str):
                    tool_input = {"input": tool_input}
                actions.append(
                    AgentAction(
                        action_type=ActionType.TOOL_CALL,
                        tool_name=tool,
                        tool_args=tool_input if isinstance(tool_input, dict) else {},
                        output=observation,
                        reasoning=getattr(lc_action, "log", ""),
                    )
                )
            except (ValueError, TypeError):
                continue

        # --- Parse final output ---
        raw_output: Any
        if isinstance(result, dict):
            raw_output = result.get(self._output_key, result)
        else:
            raw_output = result

        final_answer = self._parse_final_answer(raw_output)

        # If no intermediate steps were found, treat the whole output as a response.
        if not actions:
            actions.append(
                AgentAction(
                    action_type=ActionType.RESPONSE,
                    reasoning=str(raw_output)[:500],
                )
            )

        escalated = final_answer.get("escalated", False)
        escalation_reason = final_answer.get("escalation_reason", "")

        return AgentResponse(
            scenario_id=scenario_id,
            agent_name=self._name,
            actions=actions,
            final_answer=final_answer,
            escalated=escalated,
            escalation_reason=escalation_reason,
            total_time_ms=elapsed_ms,
        )

    # ------------------------------------------------------------------

    async def _invoke(self, invoke_input: Any) -> Any:
        """Try ainvoke, fall back to sync invoke in a thread."""
        if hasattr(self._chain, "ainvoke"):
            try:
                return await self._chain.ainvoke(invoke_input)
            except NotImplementedError:
                pass

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            _EXECUTOR, self._chain.invoke, invoke_input
        )

    @staticmethod
    def _parse_final_answer(raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
            return {"raw_response": raw}
        return {"raw_response": str(raw)}


# -------------------------------------------------------------------------
# 2. CrewAI Adapter
# -------------------------------------------------------------------------


class CrewAIAdapter(AgentAdapter):
    """Wraps a CrewAI ``Crew`` or a single CrewAI ``Agent``.

    Usage::

        from crewai import Crew, Agent
        crew = Crew(agents=[...], tasks=[...])
        adapter = CrewAIAdapter(crew=crew)

        # Or with a single agent:
        agent = Agent(role="Clinical Reviewer", ...)
        adapter = CrewAIAdapter(crew=agent, agent_name="reviewer")

    The adapter builds a CrewAI ``Task`` from the scenario, executes it via
    ``crew.kickoff()`` or ``agent.execute_task()``, and parses the output
    into an ``AgentResponse``.
    """

    def __init__(
        self,
        crew: Any,
        agent_name: str = "crewai-agent",
    ) -> None:
        self._crew = crew
        self._name = agent_name

    @property
    def name(self) -> str:
        return self._name

    async def run_scenario(
        self,
        patient_context: str,
        available_tools: list[str],
        tool_descriptions: dict[str, str],
        additional_context: dict[str, Any],
    ) -> AgentResponse:
        scenario_id = additional_context.get("scenario_id", "unknown")
        prompt = _build_user_message(
            patient_context, available_tools, tool_descriptions, additional_context
        )

        start = time.monotonic()
        try:
            raw_output = await self._execute(prompt)
        except Exception as e:
            return AgentResponse(
                scenario_id=scenario_id,
                agent_name=self._name,
                error=str(e),
                total_time_ms=(time.monotonic() - start) * 1000,
            )

        elapsed_ms = (time.monotonic() - start) * 1000

        actions, final_answer = self._parse_crew_output(raw_output)

        escalated = final_answer.get("escalated", False)
        escalation_reason = final_answer.get("escalation_reason", "")

        return AgentResponse(
            scenario_id=scenario_id,
            agent_name=self._name,
            actions=actions,
            final_answer=final_answer,
            escalated=escalated,
            escalation_reason=escalation_reason,
            total_time_ms=elapsed_ms,
        )

    # ------------------------------------------------------------------

    async def _execute(self, prompt: str) -> Any:
        """Run CrewAI Crew or Agent synchronously in a thread."""
        try:
            from crewai import Agent as CrewAgent  # noqa: F811
            from crewai import Crew, Task
        except ImportError as e:
            raise ImportError(
                "crewai is required for CrewAIAdapter. "
                "Install it with: pip install crewai"
            ) from e

        loop = asyncio.get_running_loop()

        if isinstance(self._crew, Crew):
            # If the crew already has tasks, just kick off.
            # Otherwise build a task from the prompt.
            if not self._crew.tasks:
                task = Task(
                    description=prompt,
                    expected_output="A JSON object with actions taken and a final clinical recommendation.",
                )
                self._crew.tasks = [task]

            return await loop.run_in_executor(
                _EXECUTOR, self._crew.kickoff
            )

        if isinstance(self._crew, CrewAgent):
            task = Task(
                description=prompt,
                expected_output="A JSON object with actions taken and a final clinical recommendation.",
                agent=self._crew,
            )
            return await loop.run_in_executor(
                _EXECUTOR, self._crew.execute_task, task
            )

        raise TypeError(
            f"Expected a CrewAI Crew or Agent instance, got {type(self._crew).__name__}"
        )

    @staticmethod
    def _parse_crew_output(raw: Any) -> tuple[list[AgentAction], dict[str, Any]]:
        """Parse CrewAI output into actions and final_answer."""
        actions: list[AgentAction] = []

        # CrewOutput has .raw, .json_dict, .tasks_output, etc.
        output_text: str = ""
        if hasattr(raw, "raw"):
            output_text = str(raw.raw)
        elif isinstance(raw, str):
            output_text = raw
        else:
            output_text = str(raw)

        # Try to extract structured tasks_output (list of TaskOutput).
        if hasattr(raw, "tasks_output"):
            for task_out in raw.tasks_output:
                description = getattr(task_out, "description", "")
                result = getattr(task_out, "raw", str(task_out))
                actions.append(
                    AgentAction(
                        action_type=ActionType.DECISION,
                        reasoning=description[:300],
                        output=result,
                    )
                )

        # Parse final answer from output text.
        final_answer: dict[str, Any]
        try:
            parsed = json.loads(output_text)
            if isinstance(parsed, dict):
                final_answer = parsed
            else:
                final_answer = {"raw_response": output_text}
        except (json.JSONDecodeError, TypeError):
            final_answer = {"raw_response": output_text}

        if not actions:
            actions.append(
                AgentAction(
                    action_type=ActionType.RESPONSE,
                    reasoning=output_text[:500],
                )
            )

        return actions, final_answer


# -------------------------------------------------------------------------
# 3. AutoGen Adapter
# -------------------------------------------------------------------------


class AutoGenAdapter(AgentAdapter):
    """Wraps an AutoGen ``AssistantAgent`` (v0.2 legacy or v0.4 AG2).

    Usage (v0.2)::

        from autogen import AssistantAgent, UserProxyAgent
        assistant = AssistantAgent("clinical_agent", llm_config={...})
        proxy = UserProxyAgent("user", human_input_mode="NEVER")
        adapter = AutoGenAdapter(agent=assistant, user_proxy=proxy)

    Usage (v0.4 / AG2)::

        from autogen_agentchat.agents import AssistantAgent
        agent = AssistantAgent("clinical_agent", model_client=...)
        adapter = AutoGenAdapter(agent=agent)

    The adapter initiates a chat, collects all messages, and parses tool
    calls and the final answer from the conversation history.
    """

    def __init__(
        self,
        agent: Any,
        user_proxy: Any | None = None,
        agent_name: str = "autogen-agent",
        max_turns: int = 10,
    ) -> None:
        self._agent = agent
        self._user_proxy = user_proxy
        self._name = agent_name
        self._max_turns = max_turns

    @property
    def name(self) -> str:
        return self._name

    async def run_scenario(
        self,
        patient_context: str,
        available_tools: list[str],
        tool_descriptions: dict[str, str],
        additional_context: dict[str, Any],
    ) -> AgentResponse:
        scenario_id = additional_context.get("scenario_id", "unknown")
        prompt = _build_user_message(
            patient_context, available_tools, tool_descriptions, additional_context
        )

        start = time.monotonic()
        try:
            messages = await self._run_chat(prompt)
        except Exception as e:
            return AgentResponse(
                scenario_id=scenario_id,
                agent_name=self._name,
                error=str(e),
                total_time_ms=(time.monotonic() - start) * 1000,
            )

        elapsed_ms = (time.monotonic() - start) * 1000
        actions, final_answer = self._parse_messages(messages)

        escalated = final_answer.get("escalated", False)
        escalation_reason = final_answer.get("escalation_reason", "")

        return AgentResponse(
            scenario_id=scenario_id,
            agent_name=self._name,
            actions=actions,
            final_answer=final_answer,
            escalated=escalated,
            escalation_reason=escalation_reason,
            total_time_ms=elapsed_ms,
        )

    # ------------------------------------------------------------------

    async def _run_chat(self, prompt: str) -> list[dict[str, Any]]:
        """Execute the AutoGen chat and return raw messages."""
        # Detect v0.4 (AG2) vs v0.2 (legacy pyautogen) by module path.
        agent_module = type(self._agent).__module__ or ""

        if "autogen_agentchat" in agent_module or "ag2" in agent_module:
            return await self._run_v04(prompt)
        return await self._run_v02(prompt)

    async def _run_v02(self, prompt: str) -> list[dict[str, Any]]:
        """AutoGen v0.2 (pyautogen) execution path."""
        try:
            from autogen import UserProxyAgent  # noqa: F811
        except ImportError as e:
            raise ImportError(
                "pyautogen is required for AutoGenAdapter v0.2. "
                "Install it with: pip install pyautogen"
            ) from e

        proxy = self._user_proxy
        if proxy is None:
            proxy = UserProxyAgent(
                "bench_user",
                human_input_mode="NEVER",
                max_consecutive_auto_reply=self._max_turns,
                code_execution_config=False,
            )

        loop = asyncio.get_running_loop()

        def _initiate() -> None:
            proxy.initiate_chat(
                self._agent,
                message=prompt,
                max_turns=self._max_turns,
                silent=True,
            )

        await loop.run_in_executor(_EXECUTOR, _initiate)

        # Collect messages from the agent's chat history.
        raw_messages: list[dict[str, Any]] = []
        chat_messages = getattr(self._agent, "chat_messages", {})
        for _sender, msgs in chat_messages.items():
            raw_messages.extend(msgs if isinstance(msgs, list) else [msgs])

        return raw_messages

    async def _run_v04(self, prompt: str) -> list[dict[str, Any]]:
        """AutoGen v0.4 (AG2 / autogen-agentchat) execution path."""
        try:
            from autogen_agentchat.teams import RoundRobinGroupChat
            from autogen_agentchat.conditions import TextMentionTermination
        except ImportError:
            # Fallback: try running the agent directly if teams aren't available.
            pass

        # v0.4 agents often expose an `on_messages` async method.
        if hasattr(self._agent, "on_messages"):
            try:
                from autogen_agentchat.messages import TextMessage  # type: ignore[import-untyped]
            except ImportError as e:
                raise ImportError(
                    "autogen-agentchat>=0.4 is required for AutoGenAdapter v0.4. "
                    "Install it with: pip install autogen-agentchat"
                ) from e

            user_msg = TextMessage(content=prompt, source="user")
            response = await self._agent.on_messages(
                [user_msg], cancellation_token=None
            )
            # Convert response to list-of-dicts format.
            messages: list[dict[str, Any]] = []
            if hasattr(response, "inner_messages") and response.inner_messages:
                for msg in response.inner_messages:
                    messages.append({
                        "role": getattr(msg, "source", "assistant"),
                        "content": getattr(msg, "content", str(msg)),
                    })
            if hasattr(response, "chat_message"):
                cm = response.chat_message
                messages.append({
                    "role": getattr(cm, "source", "assistant"),
                    "content": getattr(cm, "content", str(cm)),
                })
            return messages

        # Last resort: try a_initiate_chat if available.
        if hasattr(self._agent, "a_initiate_chat"):
            await self._agent.a_initiate_chat(
                message=prompt,
                max_turns=self._max_turns,
            )
            chat_messages = getattr(self._agent, "chat_messages", {})
            raw: list[dict[str, Any]] = []
            for _sender, msgs in chat_messages.items():
                raw.extend(msgs if isinstance(msgs, list) else [msgs])
            return raw

        raise RuntimeError(
            "Could not determine how to run this AutoGen agent. "
            "Ensure it is a v0.2 AssistantAgent or v0.4 autogen-agentchat agent."
        )

    @staticmethod
    def _parse_messages(
        messages: list[dict[str, Any]],
    ) -> tuple[list[AgentAction], dict[str, Any]]:
        """Extract tool calls and final answer from AutoGen message history."""
        actions: list[AgentAction] = []
        last_content: str = ""

        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "")

            # AutoGen v0.2 embeds tool calls in "function_call" or "tool_calls".
            tool_calls = msg.get("tool_calls", [])
            fn_call = msg.get("function_call")

            if tool_calls:
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    tool_name = _resolve_tool_name(fn.get("name"))
                    try:
                        args = json.loads(fn.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        args = {"raw": fn.get("arguments", "")}
                    actions.append(
                        AgentAction(
                            action_type=ActionType.TOOL_CALL,
                            tool_name=tool_name,
                            tool_args=args,
                        )
                    )
            elif fn_call:
                tool_name = _resolve_tool_name(fn_call.get("name"))
                try:
                    args = json.loads(fn_call.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {"raw": fn_call.get("arguments", "")}
                actions.append(
                    AgentAction(
                        action_type=ActionType.TOOL_CALL,
                        tool_name=tool_name,
                        tool_args=args,
                    )
                )

            if isinstance(content, str) and content.strip() and role != "tool":
                last_content = content

        # Parse final answer from last assistant message.
        final_answer: dict[str, Any]
        try:
            parsed = json.loads(last_content)
            final_answer = parsed if isinstance(parsed, dict) else {"raw_response": last_content}
        except (json.JSONDecodeError, TypeError):
            final_answer = {"raw_response": last_content} if last_content else {}

        if not actions and last_content:
            actions.append(
                AgentAction(
                    action_type=ActionType.RESPONSE,
                    reasoning=last_content[:500],
                )
            )

        return actions, final_answer


# -------------------------------------------------------------------------
# 4. Anthropic Tool-Use Adapter
# -------------------------------------------------------------------------

# Tool schemas for all 21 clinical tools, expressed as Anthropic tool definitions.
_CLINICAL_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "ehr_query",
        "description": "Query the electronic health record for patient data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "Patient identifier"},
                "query_type": {
                    "type": "string",
                    "enum": ["demographics", "diagnoses", "medications", "encounters", "vitals", "insurance"],
                    "description": "Type of data to retrieve",
                },
            },
            "required": ["patient_id"],
        },
    },
    {
        "name": "ehr_write",
        "description": "Write data to the electronic health record.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "write_type": {"type": "string", "enum": ["encounter", "diagnosis", "prescription"]},
                "data": {"type": "object"},
            },
            "required": ["patient_id", "write_type", "data"],
        },
    },
    {
        "name": "cpt_lookup",
        "description": "Look up CPT procedure codes by keyword or code.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search term or CPT code"}},
            "required": ["query"],
        },
    },
    {
        "name": "icd10_search",
        "description": "Search ICD-10 diagnosis codes.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search term or ICD-10 code"}},
            "required": ["query"],
        },
    },
    {
        "name": "claim_submit",
        "description": "Submit an insurance claim for validation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "payer": {"type": "string"},
                "codes": {"type": "array", "items": {"type": "object"}},
                "patient_age": {"type": "integer"},
            },
            "required": ["payer", "codes", "patient_age"],
        },
    },
    {
        "name": "claim_status",
        "description": "Check the status of a submitted claim.",
        "input_schema": {
            "type": "object",
            "properties": {"claim_id": {"type": "string"}},
            "required": ["claim_id"],
        },
    },
    {
        "name": "payer_rules",
        "description": "Retrieve payer-specific rules and requirements.",
        "input_schema": {
            "type": "object",
            "properties": {"payer": {"type": "string"}},
            "required": ["payer"],
        },
    },
    {
        "name": "prior_auth_submit",
        "description": "Submit a prior authorization request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "payer": {"type": "string"},
                "procedure_code": {"type": "string"},
                "patient_data": {"type": "object"},
            },
            "required": ["payer", "procedure_code", "patient_data"],
        },
    },
    {
        "name": "prior_auth_status",
        "description": "Check prior authorization status.",
        "input_schema": {
            "type": "object",
            "properties": {"auth_id": {"type": "string"}},
            "required": ["auth_id"],
        },
    },
    {
        "name": "lab_order",
        "description": "Place a laboratory order for a patient.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "lab_order": {"type": "object"},
            },
            "required": ["patient_id", "lab_order"],
        },
    },
    {
        "name": "lab_results",
        "description": "Retrieve laboratory results by order ID.",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "pharmacy_check",
        "description": "Check drug interactions and formulary coverage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "medication": {"type": "string"},
            },
            "required": ["patient_id", "medication"],
        },
    },
    {
        "name": "prescription_write",
        "description": "Write a prescription for a patient.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "prescription": {"type": "object"},
            },
            "required": ["patient_id", "prescription"],
        },
    },
    {
        "name": "scheduling_query",
        "description": "Query available appointment slots.",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider_id": {"type": "string", "default": ""},
                "specialty": {"type": "string", "default": ""},
            },
        },
    },
    {
        "name": "scheduling_book",
        "description": "Book an appointment slot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "slot_id": {"type": "string"},
                "patient_id": {"type": "string"},
            },
            "required": ["slot_id", "patient_id"],
        },
    },
    {
        "name": "referral_submit",
        "description": "Submit a referral for a patient.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "referral": {"type": "object"},
            },
            "required": ["patient_id", "referral"],
        },
    },
    {
        "name": "provider_search",
        "description": "Search for providers by specialty or location.",
        "input_schema": {
            "type": "object",
            "properties": {
                "specialty": {"type": "string", "default": ""},
                "location": {"type": "string", "default": ""},
            },
        },
    },
    {
        "name": "patient_history",
        "description": "Retrieve comprehensive patient history.",
        "input_schema": {
            "type": "object",
            "properties": {"patient_id": {"type": "string"}},
            "required": ["patient_id"],
        },
    },
    {
        "name": "insurance_verify",
        "description": "Verify patient insurance eligibility.",
        "input_schema": {
            "type": "object",
            "properties": {"patient_id": {"type": "string"}},
            "required": ["patient_id"],
        },
    },
    {
        "name": "documentation_generate",
        "description": "Generate clinical documentation from a template.",
        "input_schema": {
            "type": "object",
            "properties": {
                "template": {"type": "string"},
                "patient_id": {"type": "string"},
                "encounter_data": {"type": "object"},
            },
            "required": ["template", "patient_id"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": "Escalate the case to a human clinician.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Why escalation is needed"},
                "urgency": {"type": "string", "enum": ["low", "normal", "high", "critical"], "default": "normal"},
                "context": {"type": "object"},
            },
            "required": ["reason"],
        },
    },
]


class AnthropicToolUseAdapter(AgentAdapter):
    """Wraps the Anthropic SDK with native tool use for multi-turn clinical scenarios.

    Usage::

        adapter = AnthropicToolUseAdapter(
            model="claude-sonnet-4-20250514",
            api_key="sk-ant-...",
        )
        response = await adapter.run_scenario(patient_context, tools, ...)

    The adapter:
    * Defines all 21 clinical tools as Anthropic tool schemas.
    * Sends the scenario as a user message with tools enabled.
    * Processes ``tool_use`` content blocks as actions.
    * Handles multi-turn tool use: agent calls tool -> simulated result -> continue.
    * Uses a ``ToolRegistry`` for simulated tool results when provided.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
        agent_name: str = "anthropic-tool-use",
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        max_turns: int = 10,
        tool_registry: Any | None = None,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._name = agent_name
        self._max_tokens = max_tokens
        self._max_turns = max_turns
        self._tool_registry = tool_registry
        self._system_prompt = system_prompt or (
            "You are a healthcare AI agent being evaluated on clinical scenarios. "
            "You have access to clinical tools. Use them to gather information, "
            "make decisions, and take actions. If you are unsure or the situation "
            "requires human judgment, use the escalate_to_human tool."
        )

    @property
    def name(self) -> str:
        return self._name

    async def run_scenario(
        self,
        patient_context: str,
        available_tools: list[str],
        tool_descriptions: dict[str, str],
        additional_context: dict[str, Any],
    ) -> AgentResponse:
        scenario_id = additional_context.get("scenario_id", "unknown")

        try:
            import anthropic
        except ImportError:
            return AgentResponse(
                scenario_id=scenario_id,
                agent_name=self._name,
                error=(
                    "anthropic SDK is required for AnthropicToolUseAdapter. "
                    "Install it with: pip install anthropic"
                ),
            )

        # Filter tool schemas to only those available for this scenario.
        available_set = set(available_tools)
        tools = [t for t in _CLINICAL_TOOL_SCHEMAS if t["name"] in available_set]

        prompt = _build_user_message(
            patient_context, available_tools, tool_descriptions, additional_context
        )

        client_kwargs: dict[str, Any] = {}
        if self._api_key:
            client_kwargs["api_key"] = self._api_key
        client = anthropic.AsyncAnthropic(**client_kwargs)

        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        actions: list[AgentAction] = []
        total_tokens = 0
        escalated = False
        escalation_reason = ""

        start = time.monotonic()
        try:
            for _turn in range(self._max_turns):
                response = await client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    system=self._system_prompt,
                    messages=messages,
                    tools=tools if tools else anthropic.NOT_GIVEN,
                )

                total_tokens += (
                    (response.usage.input_tokens or 0)
                    + (response.usage.output_tokens or 0)
                )

                # Process content blocks.
                assistant_content: list[dict[str, Any]] = []
                tool_use_blocks: list[dict[str, Any]] = []
                final_text = ""

                for block in response.content:
                    if block.type == "text":
                        final_text += block.text
                        assistant_content.append(
                            {"type": "text", "text": block.text}
                        )
                    elif block.type == "tool_use":
                        tool_use_blocks.append({
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                        assistant_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                        resolved_name = _resolve_tool_name(block.name)
                        actions.append(
                            AgentAction(
                                action_type=ActionType.TOOL_CALL,
                                tool_name=resolved_name,
                                tool_args=block.input if isinstance(block.input, dict) else {},
                            )
                        )
                        if block.name == "escalate_to_human":
                            escalated = True
                            escalation_reason = (
                                block.input.get("reason", "")
                                if isinstance(block.input, dict)
                                else ""
                            )

                messages.append({"role": "assistant", "content": assistant_content})

                # If the model stopped without requesting tools, we are done.
                if response.stop_reason != "tool_use" or not tool_use_blocks:
                    break

                # Execute each tool call and feed results back.
                tool_results: list[dict[str, Any]] = []
                for tu in tool_use_blocks:
                    result = self._execute_tool(tu["name"], tu["input"])
                    # Update the last action's output.
                    for act in reversed(actions):
                        if act.tool_name == _resolve_tool_name(tu["name"]) and act.output is None:
                            act.output = result
                            break
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu["id"],
                        "content": json.dumps(result, default=str),
                    })
                messages.append({"role": "user", "content": tool_results})

        except Exception as e:
            return AgentResponse(
                scenario_id=scenario_id,
                agent_name=self._name,
                actions=actions,
                error=str(e),
                total_tokens=total_tokens,
                total_time_ms=(time.monotonic() - start) * 1000,
            )

        elapsed_ms = (time.monotonic() - start) * 1000

        # Parse final answer from the last text block.
        final_answer: dict[str, Any]
        try:
            parsed = json.loads(final_text)
            final_answer = parsed if isinstance(parsed, dict) else {"raw_response": final_text}
        except (json.JSONDecodeError, TypeError):
            final_answer = {"raw_response": final_text} if final_text else {}

        if not actions and final_text:
            actions.append(
                AgentAction(
                    action_type=ActionType.RESPONSE,
                    reasoning=final_text[:500],
                )
            )

        return AgentResponse(
            scenario_id=scenario_id,
            agent_name=self._name,
            actions=actions,
            final_answer=final_answer,
            escalated=escalated,
            escalation_reason=escalation_reason,
            total_tokens=total_tokens,
            total_time_ms=elapsed_ms,
        )

    def _execute_tool(self, tool_name: str, tool_input: Any) -> Any:
        """Execute a tool call, using the ToolRegistry if available."""
        if self._tool_registry is not None:
            args = tool_input if isinstance(tool_input, dict) else {}
            result = self._tool_registry.call(tool_name, **args)
            return dict(result) if hasattr(result, "items") else result

        # Fallback: return a simulated acknowledgement.
        return {
            "status": "simulated",
            "tool": tool_name,
            "message": f"Tool '{tool_name}' executed with input: {json.dumps(tool_input, default=str)[:200]}",
        }
