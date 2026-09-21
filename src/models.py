"""Domain models, request/result contracts, and authoritative analytical vocabulary."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

# Authoritative domain vocabulary definitions
SUPPORTED_RESULT_OPERATIONS: Set[str] = {"highest", "lowest"}
SUPPORTED_AGGREGATIONS: Set[str] = {"sum", "count", "mean", "median", "min", "max"}
ALLOWED_GROUP_BY_COLUMNS: Set[str] = {"region", "product"}
ALLOWED_FILTER_OPERATORS: Set[str] = {
    "eq",
    "neq",
    "gt",
    "gte",
    "lt",
    "lte",
    "in",
    "between",
}


@dataclass(frozen=True)
class Transaction:
    """Represents a validated transaction record."""
    id: str
    date: date
    region: str
    product: str
    units: Optional[int] = None
    unit_price: Optional[Decimal] = None
    discount: Optional[Decimal] = None


@dataclass(frozen=True)
class EvaluationQuestion:
    """Represents a benchmark evaluation question from the dataset."""
    id: str
    question: str


@dataclass(frozen=True)
class DatasetContext:
    """Immutable container holding validated transactions and evaluation questions."""
    transactions: List[Transaction]
    evaluation_questions: List[EvaluationQuestion]

    def __iter__(self):
        """Allows unpacking as (transactions, evaluation_questions)."""
        yield self.transactions
        yield self.evaluation_questions


@dataclass
class FilterClause:
    """Represents a filtering condition applied to dataset fields."""
    field: str
    operator: str  # eq, neq, gt, gte, lt, lte, in, between
    value: Any


@dataclass
class AnalysisRequest:
    """Structured request specification for the deterministic analysis engine."""
    metric: str
    aggregation: str
    filters: List[FilterClause] = field(default_factory=list)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    group_by: Optional[str] = None
    result_operation: Optional[str] = None  # "highest" | "lowest"


@dataclass
class OperationTrace:
    """Deterministic operation trace describing query resolution and execution details."""
    filters_applied: List[str] = field(default_factory=list)
    date_range_applied: Optional[str] = None
    metric: str = ""
    aggregation: str = ""
    group_by: Optional[str] = None
    matched_rows: int = 0
    excluded_rows: int = 0
    calculation_details: str = ""


@dataclass
class AnalysisResult:
    """Result of deterministic analysis computation."""
    status: str  # SUCCESS, PARTIAL, NO_DATA, UNKNOWN_DIMENSION_VALUE, INVALID_REQUEST
    metric: Optional[str] = None
    aggregation: Optional[str] = None
    value: Any = None
    grouped_values: Optional[Dict[str, Any]] = None
    group_by: Optional[str] = None
    result_operation: Optional[str] = None
    selected_group: Optional[str] = None
    matched_rows: int = 0
    excluded_missing_count: int = 0
    total_matching_records: int = 0
    trace: Optional[OperationTrace] = None
    explanation: str = ""
    error_message: Optional[str] = None
