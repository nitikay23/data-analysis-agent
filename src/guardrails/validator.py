"""Deterministic guardrail validator for tool-level safety and structural request validation."""

import logging
from typing import Any, Dict, Optional, Set, Tuple

from src.models import SUPPORTED_RESULT_OPERATIONS

logger = logging.getLogger(__name__)


class GuardrailValidator:
    """Validates tool authorization and incoming request structure before execution."""

    DEFAULT_ALLOWED_TOOLS: Set[str] = {"run_analysis"}

    def __init__(self, allowed_tools: Optional[Set[str]] = None) -> None:
        self.allowed_tools: Set[str] = allowed_tools if allowed_tools is not None else set(self.DEFAULT_ALLOWED_TOOLS)

    def validate_tool_request(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Validates tool selection and structural argument integrity.

        Returns:
            Tuple[bool, str]: (is_valid, rejection_reason)
        """
        if not tool_name or not isinstance(tool_name, str):
            logger.warning("Guardrail rejected: tool_name is empty or non-string (%s)", tool_name)
            return False, "Tool name must be a non-empty string."

        if tool_name not in self.allowed_tools:
            logger.warning("Guardrail rejected unauthorized tool invocation: '%s'", tool_name)
            return (
                False,
                f"Unauthorized tool '{tool_name}'. Allowed tools: {sorted(self.allowed_tools)}",
            )

        if not isinstance(arguments, dict):
            logger.warning("Guardrail rejected non-dictionary arguments payload for tool '%s'", tool_name)
            return False, "Tool arguments must be provided as a dictionary."

        # Specific structural checks for 'run_analysis'
        if tool_name == "run_analysis":
            metric = arguments.get("metric")
            if not metric or not isinstance(metric, str):
                return False, "Missing or invalid required argument 'metric' (must be a non-empty string)."

            aggregation = arguments.get("aggregation")
            if not aggregation or not isinstance(aggregation, str):
                return False, "Missing or invalid required argument 'aggregation' (must be a non-empty string)."

            filters = arguments.get("filters")
            if filters is not None:
                if not isinstance(filters, list):
                    return False, "Argument 'filters' must be a list of filter clauses."
                for idx, f in enumerate(filters):
                    if not isinstance(f, dict):
                        return False, f"Filter at index {idx} must be a dictionary."
                    if "field" not in f or "operator" not in f or "value" not in f:
                        return (
                            False,
                            f"Filter at index {idx} is missing required fields ('field', 'operator', 'value').",
                        )

            group_by = arguments.get("group_by")
            if group_by is not None and not isinstance(group_by, str):
                return False, "Argument 'group_by' must be a string or None."

            result_operation = arguments.get("result_operation")
            if result_operation is not None:
                if not isinstance(result_operation, str) or result_operation not in SUPPORTED_RESULT_OPERATIONS:
                    return (
                        False,
                        f"Argument 'result_operation' must be one of {sorted(SUPPORTED_RESULT_OPERATIONS)}, got '{result_operation}'.",
                    )
                if not group_by:
                    return False, "Argument 'result_operation' requires 'group_by' to be specified."

        logger.info("Guardrail successfully validated tool request for '%s'", tool_name)
        return True, ""
