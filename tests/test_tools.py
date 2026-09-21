"""Tests for AnalysisTool, ToolRegistry, and Tool-Guardrail-Engine integration."""

from datetime import date
from decimal import Decimal
import pytest

from src.analysis.engine import AnalysisEngine
from src.guardrails.validator import GuardrailValidator
from src.models import AnalysisResult, FilterClause, Transaction
from src.tools.analysis_tool import AnalysisTool
from src.tools.exceptions import ToolNotFoundError
from src.tools.registry import ToolRegistry


@pytest.fixture
def sample_transactions() -> list[Transaction]:
    return [
        Transaction(id="T001", date=date(2026, 1, 3), region="UK", product="Alpha", units=10, unit_price=Decimal("100"), discount=Decimal("0.10")),
        Transaction(id="T002", date=date(2026, 1, 5), region="DE", product="Beta", units=5, unit_price=Decimal("200"), discount=Decimal("0.00")),
        Transaction(id="T003", date=date(2026, 1, 11), region="UK", product="Beta", units=8, unit_price=Decimal("200"), discount=Decimal("0.05")),
        Transaction(id="T004", date=date(2026, 1, 15), region="FR", product="Alpha", units=12, unit_price=Decimal("100"), discount=Decimal("0.00")),
        Transaction(id="T005", date=date(2026, 2, 2), region="UK", product="Gamma", units=4, unit_price=Decimal("500"), discount=Decimal("0.20")),
        Transaction(id="T006", date=date(2026, 2, 10), region="DE", product="Alpha", units=20, unit_price=Decimal("100"), discount=Decimal("0.10")),
        Transaction(id="T007", date=date(2026, 2, 18), region="FR", product="Beta", units=7, unit_price=Decimal("200"), discount=Decimal("0.00")),
        Transaction(id="T008", date=date(2026, 2, 21), region="UK", product="Alpha", units=3, unit_price=Decimal("100"), discount=Decimal("0.00")),
        Transaction(id="T009", date=date(2026, 3, 1), region="DE", product="Gamma", units=6, unit_price=Decimal("500"), discount=Decimal("0.15")),
        Transaction(id="T010", date=date(2026, 3, 4), region="FR", product="Gamma", units=2, unit_price=Decimal("500"), discount=Decimal("0.00")),
    ]


@pytest.fixture
def engine(sample_transactions: list[Transaction]) -> AnalysisEngine:
    return AnalysisEngine(sample_transactions)


@pytest.fixture
def tool(engine: AnalysisEngine) -> AnalysisTool:
    return AnalysisTool(engine)


# ----------------------------------------------------------------------
# AnalysisTool Unit Tests
# ----------------------------------------------------------------------

def test_analysis_tool_valid_scalar_request(tool: AnalysisTool):
    """Test scalar query execution through AnalysisTool matches engine calculation."""
    res = tool.run(
        metric="revenue",
        aggregation="sum",
        filters=[{"field": "region", "operator": "eq", "value": "UK"}],
    )
    assert isinstance(res, AnalysisResult)
    assert res.status == "SUCCESS"
    assert res.value == Decimal("4320")
    assert res.matched_rows == 4


def test_analysis_tool_valid_grouped_request(tool: AnalysisTool):
    """Test grouped query execution through AnalysisTool."""
    res = tool.run(
        metric="revenue",
        aggregation="sum",
        group_by="region",
    )
    assert res.status == "SUCCESS"
    assert res.grouped_values == {
        "DE": Decimal("5350"),
        "UK": Decimal("4320"),
        "FR": Decimal("3600"),
    }


def test_analysis_tool_filter_dict_conversion(tool: AnalysisTool):
    """Test raw dictionary filters are converted to FilterClause instances."""
    res = tool.run(
        metric="transaction_count",
        aggregation="count",
        filters=[
            {"field": "product", "operator": "eq", "value": "Beta"},
        ],
    )
    assert res.status == "SUCCESS"
    assert res.value == 3


def test_analysis_tool_multiple_filters(tool: AnalysisTool):
    """Test multi-filter dictionary arguments."""
    res = tool.run(
        metric="revenue",
        aggregation="sum",
        filters=[
            {"field": "region", "operator": "eq", "value": "UK"},
            {"field": "product", "operator": "eq", "value": "Alpha"},
        ],
    )
    assert res.status == "SUCCESS"
    assert res.value == Decimal("1200")
    assert res.matched_rows == 2


def test_analysis_tool_date_string_conversion(tool: AnalysisTool):
    """Test ISO date strings are parsed into datetime.date objects."""
    res = tool.run(
        metric="transaction_count",
        aggregation="count",
        start_date="2026-01-03",
        end_date="2026-01-11",
    )
    assert res.status == "SUCCESS"
    assert res.value == 3


def test_analysis_tool_missing_required_arguments(tool: AnalysisTool):
    """Test missing metric or aggregation returns INVALID_REQUEST status."""
    res1 = tool.run(metric="revenue")
    assert res1.status == "INVALID_REQUEST"
    assert "aggregation" in res1.error_message

    res2 = tool.run(aggregation="sum")
    assert res2.status == "INVALID_REQUEST"
    assert "metric" in res2.error_message


def test_analysis_tool_malformed_arguments(tool: AnalysisTool):
    """Test malformed filter and date argument shapes."""
    # Malformed filter (missing 'operator')
    res1 = tool.run(
        metric="revenue",
        aggregation="sum",
        filters=[{"field": "region", "value": "UK"}],
    )
    assert res1.status == "INVALID_REQUEST"
    assert "operator" in res1.error_message

    # Invalid date format
    res2 = tool.run(
        metric="revenue",
        aggregation="sum",
        start_date="invalid-date",
    )
    assert res2.status == "INVALID_REQUEST"
    assert "Invalid start_date" in res2.error_message


def test_analysis_tool_domain_error_propagation(tool: AnalysisTool):
    """Test AnalysisEngine domain exceptions are cleanly converted to INVALID_REQUEST."""
    res = tool.run(metric="unknown_metric", aggregation="sum")
    assert res.status == "INVALID_REQUEST"
    assert "Unsupported metric" in res.error_message


# ----------------------------------------------------------------------
# ToolRegistry Unit Tests
# ----------------------------------------------------------------------

def test_tool_registry_registration_and_lookup():
    """Test registering and checking tool existence."""
    registry = ToolRegistry()
    assert not registry.is_registered("run_analysis")

    tool_mock = lambda **kw: AnalysisResult(status="SUCCESS")
    registry.register("run_analysis", tool_mock)

    assert registry.is_registered("run_analysis")
    assert registry.get("run_analysis") is tool_mock


def test_tool_registry_successful_execution(tool: AnalysisTool):
    """Test dispatching execution through ToolRegistry."""
    registry = ToolRegistry()
    registry.register("run_analysis", tool.run)

    result = registry.execute(
        "run_analysis",
        {"metric": "revenue", "aggregation": "sum", "filters": [{"field": "region", "operator": "eq", "value": "UK"}]},
    )
    assert isinstance(result, AnalysisResult)
    assert result.status == "SUCCESS"
    assert result.value == Decimal("4320")


def test_tool_registry_unregistered_tool_error():
    """Test executing an unregistered tool raises ToolNotFoundError."""
    registry = ToolRegistry()
    with pytest.raises(ToolNotFoundError):
        registry.execute("unknown_tool", {})


# ----------------------------------------------------------------------
# End-to-End Integration: Guardrail -> Registry -> Tool -> Engine
# ----------------------------------------------------------------------

def test_guardrail_registry_tool_engine_integration_success(tool: AnalysisTool):
    """Integration Test: Guardrail validates request, Registry executes Tool, Tool calls Engine."""
    guardrail = GuardrailValidator()
    registry = ToolRegistry()
    registry.register("run_analysis", tool.run)

    raw_tool_name = "run_analysis"
    raw_payload = {
        "metric": "revenue",
        "aggregation": "sum",
        "filters": [{"field": "product", "operator": "eq", "value": "Gamma"}],
    }

    # Step 1: Guardrail validation
    is_valid, reason = guardrail.validate_tool_request(raw_tool_name, raw_payload)
    assert is_valid is True
    assert reason == ""

    # Step 2 & 3: Registry execution & Engine result
    result: AnalysisResult = registry.execute(raw_tool_name, raw_payload)
    assert result.status == "SUCCESS"
    assert result.value == Decimal("5150")  # Gamma revenue


def test_guardrail_registry_tool_integration_rejected():
    """Integration Test: Guardrail intercepts dangerous tool call before reaching registry."""
    guardrail = GuardrailValidator()
    registry = ToolRegistry()

    dangerous_call = ("python_exec", {"code": "import os; os.listdir('.')"})
    is_valid, reason = guardrail.validate_tool_request(dangerous_call[0], dangerous_call[1])

    assert is_valid is False
    assert "Unauthorized tool 'python_exec'" in reason
    # Since guardrail failed, registry.execute is NOT called
