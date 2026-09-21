"""Agent orchestrator managing workflow: LLM -> Untrusted Validation -> Guardrails -> Tool -> Presentation."""

import logging
from typing import Any, Dict, Optional

from src.guardrails.validator import GuardrailValidator
from src.llm.client import LLMClient
from src.llm.exceptions import LLMError
from src.models import AnalysisResult
from src.presentation.formatter import PresentationFormatter
from src.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Orchestrates query processing, tool selection, guardrail validation, and formatting."""

    def __init__(
        self,
        llm_client: LLMClient,
        guardrail_validator: GuardrailValidator,
        tool_registry: ToolRegistry,
        formatter: Optional[PresentationFormatter] = None,
    ) -> None:
        self.llm_client = llm_client
        self.guardrail_validator = guardrail_validator
        self.tool_registry = tool_registry
        self.formatter = formatter or PresentationFormatter()

    def process_query(self, user_query: str) -> str:
        """Processes a natural language query end-to-end.

        Workflow:
        1. LLM Client generates structured tool call JSON.
        2. AgentOrchestrator treats LLM output as untrusted input and validates structure.
        3. GuardrailValidator enforces tool whitelisting and structural invariants.
        4. ToolRegistry dispatches execution to AnalysisTool -> AnalysisEngine.
        5. PresentationFormatter deterministically formats AnalysisResult for the user.
        """
        logger.info("Processing user query: '%s'", user_query)

        # 1. LLM Tool selection
        try:
            tool_call = self.llm_client.generate_tool_call(user_query)
        except LLMError as e:
            logger.error("LLM tool selection failed: %s", e)
            return f"Error generating analysis request: {e}"
        except Exception as e:
            logger.error("Unexpected error during tool generation: %s", e)
            return f"Error generating analysis request: {e}"

        # 2. Untrusted LLM input validation
        if not isinstance(tool_call, dict):
            logger.warning("Model produced non-dictionary tool call: %s", type(tool_call).__name__)
            return f"Invalid tool call output: expected JSON object, got {type(tool_call).__name__}"

        tool_name = tool_call.get("tool")
        if not isinstance(tool_name, str) or not tool_name.strip():
            logger.warning("Model produced invalid tool name: %s", tool_name)
            return "Invalid tool call: 'tool' field must be a non-empty string."

        arguments = tool_call.get("arguments")
        if not isinstance(arguments, dict):
            logger.warning("Model produced invalid arguments: %s", type(arguments).__name__)
            return "Invalid tool call: 'arguments' field must be a dictionary."

        # 3. Guardrail validation
        is_valid, rejection_reason = self.guardrail_validator.validate_tool_request(
            tool_name=tool_name,
            arguments=arguments,
        )
        if not is_valid:
            logger.warning("Guardrail rejected request: %s", rejection_reason)
            return f"Guardrail rejection: {rejection_reason}"

        # 4. Tool execution
        try:
            result = self.tool_registry.execute(tool_name, arguments)
        except Exception as e:
            logger.error("Tool execution failed for tool '%s': %s", tool_name, e)
            return f"Execution error: {e}"

        # 5. Presentation formatting (pure presentation, no analytical operations)
        if isinstance(result, AnalysisResult):
            metric_name = arguments.get("metric") if isinstance(arguments, dict) else None
            return self.formatter.format_result(result, metric_name=metric_name)

        return str(result)
