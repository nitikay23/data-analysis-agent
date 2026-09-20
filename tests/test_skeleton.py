"""Tests verifying the project skeleton and module imports."""

from pathlib import Path

from src.agent.orchestrator import AgentOrchestrator
from src.analysis.engine import AnalysisEngine
from src.analysis.metrics import MetricsCalculator
from src.config import config
from src.data.loader import DataLoader
from src.data.schema import DatasetSchema
from src.guardrails.validator import GuardrailValidator
from src.llm.client import LLMClient
from src.models import AnalysisRequest, AnalysisResult, FilterClause, Transaction
from src.presentation.formatter import PresentationFormatter
from src.tools.analysis_tool import AnalysisTool
from src.tools.registry import ToolRegistry


def test_config_defaults():
    assert config is not None
    assert isinstance(config.data_path, Path)


def test_schema_constants():
    assert "revenue" in DatasetSchema.METRICS
    assert "UK" in DatasetSchema.TRUSTED_REGIONS
    assert "Alpha" in DatasetSchema.TRUSTED_PRODUCTS
    assert "sum" in DatasetSchema.AGGREGATIONS
    assert "eq" in DatasetSchema.FILTER_OPERATORS


def test_registry():
    registry = ToolRegistry()
    assert not registry.is_registered("run_analysis")
    registry.register("run_analysis", lambda **kw: None)
    assert registry.is_registered("run_analysis")
    assert registry.get("run_analysis") is not None


def test_models_instantiation():
    req = AnalysisRequest(metric="revenue", aggregation="sum")
    assert req.metric == "revenue"
    assert req.aggregation == "sum"
    assert req.filters == []

    res = AnalysisResult(status="NO_DATA")
    assert res.status == "NO_DATA"
