"""Raw input and trusted data-view schema definitions.

Defines the boundary between raw CSV input schema and trusted internal data views:
- RawCSVSchema: Expected structural schema of the incoming raw CSV
- TransactionSchema: Trusted fields and schema for transaction records
- EvaluationQuestionSchema: Trusted fields and schema for evaluation questions
"""

from typing import Set


class RawCSVSchema:
    """Expected structural schema of the external/raw input CSV."""

    REQUIRED_COLUMNS: Set[str] = {
        "id",
        "date",
        "region",
        "product",
        "units",
        "unit_price",
        "discount",
        "question",
    }
    TRANSACTION_ID_PREFIX: str = "T"
    EVALUATION_ID_PREFIX: str = "Q"


class TransactionSchema:
    """Trusted schema for transaction records after classification and separation."""

    COLUMNS: Set[str] = {
        "id",
        "date",
        "region",
        "product",
        "units",
        "unit_price",
        "discount",
    }
    REQUIRED_FIELDS: Set[str] = {"id", "date", "region", "product"}
    NUMERIC_FIELDS: Set[str] = {"units", "unit_price", "discount"}


class EvaluationQuestionSchema:
    """Trusted schema for evaluation question records."""

    COLUMNS: Set[str] = {"id", "question"}
    REQUIRED_FIELDS: Set[str] = {"id", "question"}
