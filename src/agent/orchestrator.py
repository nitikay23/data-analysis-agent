"""Agent orchestrator managing workflow: LLM -> Guardrails -> Tool -> Presentation."""

from typing import Any, Dict

from src.guardrails.validator import GuardrailValidator
from src.llm.client import LLMClient
from src.presentation.formatter import PresentationFormatter
from src.tools.registry import ToolRegistry


class AgentOrchestrator:
    """Orchestrates query processing, tool selection, guardrail validation, and formatting."""

    def __init__(
        self,
        llm_client: LLMClient,
        guardrail_validator: GuardrailValidator,
        tool_registry: ToolRegistry,
        formatter: PresentationFormatter,
    ) -> None:
        self.llm_client = llm_client
        self.guardrail_validator = guardrail_validator
        self.tool_registry = tool_registry
        self.formatter = formatter

    def process_query(self, user_query: str) -> str:
        """Processes a natural language query end-to-end."""
        # Workflow implementation in Phase 5
        return "Not implemented yet"
