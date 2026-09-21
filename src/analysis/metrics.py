"""Centralized metric registry and exact Decimal calculation semantics.

This module is the single source of truth for supported analytical metrics,
their calculation formulas, and their numeric type contracts.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Dict, Optional, Set


@dataclass(frozen=True)
class MetricDefinition:
    """Metadata specification for a supported metric with optional dynamic compute function."""

    name: str
    is_derived: bool
    is_decimal: bool
    is_count: bool
    description: str
    compute_fn: Optional[Callable[[Dict[str, Any]], Optional[Decimal]]] = None


def compute_gross_amount(
    units: Optional[int], unit_price: Optional[Decimal]
) -> Optional[Decimal]:
    """gross_amount = units * unit_price (exact Decimal)."""
    if units is None or unit_price is None:
        return None
    return Decimal(units) * unit_price


def compute_discount_amount(
    gross_amount: Optional[Decimal], discount: Optional[Decimal]
) -> Optional[Decimal]:
    """discount_amount = gross_amount * discount (exact Decimal)."""
    if gross_amount is None or discount is None:
        return None
    return gross_amount * discount


def compute_revenue(
    units: Optional[int],
    unit_price: Optional[Decimal],
    discount: Optional[Decimal],
) -> Optional[Decimal]:
    """revenue = gross_amount - discount_amount = units * unit_price * (1 - discount)."""
    if units is None or unit_price is None or discount is None:
        return None
    gross = Decimal(units) * unit_price
    disc_val = gross * discount
    return gross - disc_val


METRIC_REGISTRY: Dict[str, MetricDefinition] = {
    "units": MetricDefinition(
        name="units",
        is_derived=False,
        is_decimal=False,
        is_count=False,
        description="Number of physical units",
        compute_fn=None,
    ),
    "unit_price": MetricDefinition(
        name="unit_price",
        is_derived=False,
        is_decimal=True,
        is_count=False,
        description="Price per single unit (Decimal)",
        compute_fn=None,
    ),
    "discount": MetricDefinition(
        name="discount",
        is_derived=False,
        is_decimal=True,
        is_count=False,
        description="Discount fraction applied (Decimal, e.g. 0.10 for 10%)",
        compute_fn=None,
    ),
    "gross_amount": MetricDefinition(
        name="gross_amount",
        is_derived=True,
        is_decimal=True,
        is_count=False,
        description="Pre-discount total: units * unit_price",
        compute_fn=lambda r: compute_gross_amount(r.get("units"), r.get("unit_price")),
    ),
    "discount_amount": MetricDefinition(
        name="discount_amount",
        is_derived=True,
        is_decimal=True,
        is_count=False,
        description="Total monetary discount: gross_amount * discount",
        compute_fn=lambda r: compute_discount_amount(
            r.get("gross_amount", compute_gross_amount(r.get("units"), r.get("unit_price"))),
            r.get("discount"),
        ),
    ),
    "revenue": MetricDefinition(
        name="revenue",
        is_derived=True,
        is_decimal=True,
        is_count=False,
        description="Net revenue: gross_amount - discount_amount",
        compute_fn=lambda r: compute_revenue(
            r.get("units"), r.get("unit_price"), r.get("discount")
        ),
    ),
    "transaction_count": MetricDefinition(
        name="transaction_count",
        is_derived=True,
        is_decimal=False,
        is_count=True,
        description="Count of filtered transaction records",
        compute_fn=None,
    ),
}

SUPPORTED_METRICS: Set[str] = set(METRIC_REGISTRY.keys())


class MetricsCalculator:
    """Calculates derived metrics using exact Decimal arithmetic without intermediate rounding."""

    @staticmethod
    def calculate_gross_amount(
        units: Optional[int], unit_price: Optional[Decimal]
    ) -> Optional[Decimal]:
        """Calculates pre-discount gross amount: units * unit_price."""
        return compute_gross_amount(units, unit_price)

    @staticmethod
    def calculate_discount_amount(
        gross_amount: Optional[Decimal], discount: Optional[Decimal]
    ) -> Optional[Decimal]:
        """Calculates discount amount: gross_amount * discount."""
        return compute_discount_amount(gross_amount, discount)

    @staticmethod
    def calculate_revenue(
        gross_amount: Optional[Decimal], discount_amount: Optional[Decimal]
    ) -> Optional[Decimal]:
        """Calculates net revenue: gross_amount - discount_amount."""
        if gross_amount is None or discount_amount is None:
            return None
        return gross_amount - discount_amount

    @staticmethod
    def calculate_row_revenue(
        units: Optional[int],
        unit_price: Optional[Decimal],
        discount: Optional[Decimal],
    ) -> Optional[Decimal]:
        """Calculates net revenue directly from row primitives."""
        return compute_revenue(units, unit_price, discount)

    @staticmethod
    def is_supported(metric_name: str) -> bool:
        """Returns True if the metric is registered."""
        return metric_name in SUPPORTED_METRICS

    @staticmethod
    def get_definition(metric_name: str) -> MetricDefinition:
        """Returns the metric definition or raises KeyError."""
        if metric_name not in METRIC_REGISTRY:
            raise KeyError(f"Unsupported metric '{metric_name}'")
        return METRIC_REGISTRY[metric_name]
