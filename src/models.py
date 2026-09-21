"""Domain models and data contracts."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, List, Optional


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
    group_by: Optional[str] = None


@dataclass
class AnalysisResult:
    """Result of deterministic analysis computation."""
    status: str  # SUCCESS, NO_DATA, ERROR
    value: Any = None
    grouped_values: Optional[dict] = None
    excluded_missing_count: int = 0
    total_matching_records: int = 0
    explanation: str = ""
    error_message: Optional[str] = None
