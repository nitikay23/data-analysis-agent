"""Deterministic analysis engine and metric calculation package."""

from src.analysis.engine import AnalysisEngine
from src.analysis.exceptions import (
    AnalysisError,
    InvalidDateRangeError,
    InvalidFilterValueError,
    InvalidRequestError,
    UnsupportedAggregationError,
    UnsupportedFilterColumnError,
    UnsupportedGroupByError,
    UnsupportedMetricError,
    UnsupportedOperatorError,
)
from src.analysis.metrics import (
    METRIC_REGISTRY,
    SUPPORTED_METRICS,
    MetricDefinition,
    MetricsCalculator,
)

__all__ = [
    "AnalysisEngine",
    "MetricsCalculator",
    "MetricDefinition",
    "METRIC_REGISTRY",
    "SUPPORTED_METRICS",
    "AnalysisError",
    "InvalidRequestError",
    "UnsupportedMetricError",
    "UnsupportedAggregationError",
    "UnsupportedFilterColumnError",
    "UnsupportedOperatorError",
    "UnsupportedGroupByError",
    "InvalidFilterValueError",
    "InvalidDateRangeError",
]
