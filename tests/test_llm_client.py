"""Unit tests for the LLM Client and Prompt construction."""

import json
import pytest

from src.llm.client import MockLLMClient, OllamaLLMClient
from src.llm.exceptions import LLMResponseParsingError
from src.llm.prompts import build_system_prompt


class TestLLMPrompts:
    """Tests dynamic system prompt construction."""

    def test_build_system_prompt_contains_supported_vocab(self) -> None:
        prompt = build_system_prompt()
        assert "run_analysis" in prompt
        assert "revenue" in prompt
        assert "units" in prompt
        assert "transaction_count" in prompt
        assert "region" in prompt
        assert "product" in prompt
        assert "sum" in prompt
        assert "mean" in prompt
        assert "median" in prompt
        assert "count" in prompt
        assert "eq" in prompt
        assert "gt" in prompt
        assert "JSON" in prompt


class TestOllamaLLMClientParsing:
    """Tests response extraction and JSON parsing logic."""

    def test_extract_pure_json(self) -> None:
        raw = '{"tool": "run_analysis", "arguments": {"metric": "revenue", "aggregation": "sum"}}'
        result = OllamaLLMClient._extract_json_tool_call(raw)
        assert result["tool"] == "run_analysis"
        assert result["arguments"]["metric"] == "revenue"

    def test_extract_markdown_fenced_json(self) -> None:
        raw = """Here is the tool call:
```json
{
    "tool": "run_analysis",
    "arguments": {
        "metric": "units",
        "aggregation": "mean"
    }
}
```
"""
        result = OllamaLLMClient._extract_json_tool_call(raw)
        assert result["tool"] == "run_analysis"
        assert result["arguments"]["aggregation"] == "mean"

    def test_extract_invalid_json_raises_error(self) -> None:
        raw = "I am an LLM and I cannot answer this in JSON."
        with pytest.raises(LLMResponseParsingError):
            OllamaLLMClient._extract_json_tool_call(raw)


class TestMockLLMClient:
    """Tests deterministic mock client for evaluation queries."""

    def test_benchmark_q001_mapping(self) -> None:
        mock = MockLLMClient()
        call = mock.generate_tool_call("What is the total revenue for UK transactions?")
        assert call["tool"] == "run_analysis"
        assert call["arguments"]["metric"] == "revenue"
        assert call["arguments"]["aggregation"] == "sum"
        assert call["arguments"]["filters"] == [{"field": "region", "operator": "eq", "value": "UK"}]

    def test_custom_mapping_override(self) -> None:
        mock = MockLLMClient()
        mock.register_mapping(
            "custom question",
            {"tool": "run_analysis", "arguments": {"metric": "revenue", "aggregation": "max"}},
        )
        call = mock.generate_tool_call("custom question")
        assert call["arguments"]["aggregation"] == "max"
