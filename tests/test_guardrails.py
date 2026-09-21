"""Tests for GuardrailValidator tool safety, whitelisting, and structural validation."""

import pytest
from src.guardrails.validator import GuardrailValidator


@pytest.fixture
def validator() -> GuardrailValidator:
    return GuardrailValidator()


def test_valid_run_analysis_request_accepted(validator: GuardrailValidator):
    """Test valid run_analysis request with complete arguments is accepted."""
    args = {
        "metric": "revenue",
        "aggregation": "sum",
        "filters": [{"field": "region", "operator": "eq", "value": "UK"}],
        "group_by": "region",
    }
    is_valid, reason = validator.validate_tool_request("run_analysis", args)
    assert is_valid is True
    assert reason == ""


def test_unauthorized_tool_names_rejected(validator: GuardrailValidator):
    """Test unauthorized tool names (python_exec, eval, bash, inspect_files) are rejected."""
    dangerous_tools = ["python_exec", "eval", "bash", "execute_code", "read_file", "system_cmd"]
    for tool in dangerous_tools:
        is_valid, reason = validator.validate_tool_request(tool, {"code": "import os"})
        assert is_valid is False
        assert "Unauthorized tool" in reason
        assert tool in reason


def test_empty_or_non_string_tool_name_rejected(validator: GuardrailValidator):
    """Test empty string or invalid tool_name types are rejected."""
    is_valid, reason = validator.validate_tool_request("", {"metric": "revenue", "aggregation": "sum"})
    assert is_valid is False
    assert "non-empty string" in reason

    is_valid_none, _ = validator.validate_tool_request(None, {})  # type: ignore
    assert is_valid_none is False


def test_non_dict_arguments_rejected(validator: GuardrailValidator):
    """Test non-dictionary arguments payload is rejected."""
    is_valid, reason = validator.validate_tool_request("run_analysis", "metric=revenue")  # type: ignore
    assert is_valid is False
    assert "must be provided as a dictionary" in reason


def test_missing_required_structural_arguments_rejected(validator: GuardrailValidator):
    """Test missing required arguments 'metric' or 'aggregation' are rejected."""
    # Missing aggregation
    is_valid1, reason1 = validator.validate_tool_request("run_analysis", {"metric": "revenue"})
    assert is_valid1 is False
    assert "aggregation" in reason1

    # Missing metric
    is_valid2, reason2 = validator.validate_tool_request("run_analysis", {"aggregation": "sum"})
    assert is_valid2 is False
    assert "metric" in reason2


def test_invalid_filter_structure_rejected(validator: GuardrailValidator):
    """Test malformed filter structures (non-list or missing keys) are rejected."""
    # filters not a list
    is_valid1, reason1 = validator.validate_tool_request(
        "run_analysis",
        {"metric": "revenue", "aggregation": "sum", "filters": "region eq UK"},
    )
    assert is_valid1 is False
    assert "must be a list" in reason1

    # filter item not a dictionary
    is_valid2, reason2 = validator.validate_tool_request(
        "run_analysis",
        {"metric": "revenue", "aggregation": "sum", "filters": ["invalid"]},
    )
    assert is_valid2 is False
    assert "must be a dictionary" in reason2

    # filter item missing required keys
    is_valid3, reason3 = validator.validate_tool_request(
        "run_analysis",
        {"metric": "revenue", "aggregation": "sum", "filters": [{"field": "region", "operator": "eq"}]},
    )
    assert is_valid3 is False
    assert "missing required fields" in reason3


def test_custom_allowed_tools_configuration():
    """Test GuardrailValidator with customized allowed_tools set."""
    custom_validator = GuardrailValidator(allowed_tools={"custom_tool"})
    assert custom_validator.validate_tool_request("custom_tool", {}) == (True, "")
    assert custom_validator.validate_tool_request("run_analysis", {})[0] is False
