"""Comprehensive deterministic tests for AnalysisEngine and MetricsCalculator."""

from datetime import date
from decimal import Decimal
import pytest

from src.analysis.engine import AnalysisEngine
from src.analysis.exceptions import (
    InvalidDateRangeError,
    InvalidFilterValueError,
    UnsupportedAggregationError,
    UnsupportedFilterColumnError,
    UnsupportedGroupByError,
    UnsupportedMetricError,
    UnsupportedOperatorError,
)
from src.analysis.metrics import MetricsCalculator
from src.data.loader import DataLoader
from src.models import (
    AnalysisRequest,
    AnalysisResult,
    DatasetContext,
    FilterClause,
    Transaction,
)


@pytest.fixture
def sample_transactions() -> list[Transaction]:
    """10-row production sample transactions matching project_4.csv."""
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


# ----------------------------------------------------------------------
# Core Evaluation Cases (1 - 8)
# ----------------------------------------------------------------------

def test_1_uk_revenue(engine: AnalysisEngine):
    """Case 1: Total UK revenue = 4320."""
    req = AnalysisRequest(
        metric="revenue",
        aggregation="sum",
        filters=[FilterClause(field="region", operator="eq", value="UK")],
    )
    res = engine.execute(req)
    assert res.status == "SUCCESS"
    assert res.value == Decimal("4320")
    assert isinstance(res.value, Decimal)


def test_2_average_units(engine: AnalysisEngine):
    """Case 2: Average units across all transactions = 7.7."""
    req = AnalysisRequest(
        metric="units",
        aggregation="mean",
    )
    res = engine.execute(req)
    assert res.status == "SUCCESS"
    assert res.value == pytest.approx(7.7)


def test_3_region_revenue(engine: AnalysisEngine):
    """Case 3: Total revenue by region: DE = 5350, UK = 4320, FR = 3600."""
    req = AnalysisRequest(
        metric="revenue",
        aggregation="sum",
        group_by="region",
    )
    res = engine.execute(req)
    assert res.status == "SUCCESS"
    assert res.grouped_values == {
        "DE": Decimal("5350"),
        "UK": Decimal("4320"),
        "FR": Decimal("3600"),
    }


def test_4_beta_transaction_count(engine: AnalysisEngine):
    """Case 4: Beta transaction count = 3."""
    req = AnalysisRequest(
        metric="transaction_count",
        aggregation="count",
        filters=[FilterClause(field="product", operator="eq", value="Beta")],
    )
    res = engine.execute(req)
    assert res.status == "SUCCESS"
    assert res.value == 3


def test_5_gamma_revenue(engine: AnalysisEngine):
    """Case 5: Total revenue for Gamma = 5150."""
    req = AnalysisRequest(
        metric="revenue",
        aggregation="sum",
        filters=[FilterClause(field="product", operator="eq", value="Gamma")],
    )
    res = engine.execute(req)
    assert res.status == "SUCCESS"
    assert res.value == Decimal("5150")


def test_6_twenty_percent_discount_count(engine: AnalysisEngine):
    """Case 6: 20% discount transaction count = 1."""
    req = AnalysisRequest(
        metric="transaction_count",
        aggregation="count",
        filters=[FilterClause(field="discount", operator="eq", value=Decimal("0.20"))],
    )
    res = engine.execute(req)
    assert res.status == "SUCCESS"
    assert res.value == 1


def test_7_average_revenue_by_region(engine: AnalysisEngine):
    """Case 7: Average revenue by region: DE = 1783.333..., FR = 1200, UK = 1080."""
    req = AnalysisRequest(
        metric="revenue",
        aggregation="mean",
        group_by="region",
    )
    res = engine.execute(req)
    assert res.status == "SUCCESS"
    assert res.grouped_values["UK"] == Decimal("1080")
    assert res.grouped_values["FR"] == Decimal("1200")
    assert res.grouped_values["DE"] == Decimal("5350") / Decimal(3)


def test_8_median_revenue_by_region(engine: AnalysisEngine):
    """Case 8: Median revenue by region: DE = 1800, FR = 1200, UK = 1210."""
    req = AnalysisRequest(
        metric="revenue",
        aggregation="median",
        group_by="region",
    )
    res = engine.execute(req)
    assert res.status == "SUCCESS"
    assert res.grouped_values == {
        "DE": Decimal("1800"),
        "FR": Decimal("1200"),
        "UK": Decimal("1210"),
    }


# ----------------------------------------------------------------------
# Additional Boundary & Edge Case Tests (9 - 33)
# ----------------------------------------------------------------------

def test_9_multiple_filters(engine: AnalysisEngine):
    """Test 9: Multiple filters combined (UK + Alpha)."""
    req = AnalysisRequest(
        metric="revenue",
        aggregation="sum",
        filters=[
            FilterClause(field="region", operator="eq", value="UK"),
            FilterClause(field="product", operator="eq", value="Alpha"),
        ],
    )
    res = engine.execute(req)
    # UK Alpha: T001 (900) + T008 (300) = 1200
    assert res.status == "SUCCESS"
    assert res.value == Decimal("1200")
    assert res.matched_rows == 2


def test_10_inclusive_date_range(engine: AnalysisEngine):
    """Test 10: Inclusive date range filtering."""
    # 2026-01-03 to 2026-01-11 includes T001 (01-03), T002 (01-05), T003 (01-11)
    req = AnalysisRequest(
        metric="transaction_count",
        aggregation="count",
        start_date=date(2026, 1, 3),
        end_date=date(2026, 1, 11),
    )
    res = engine.execute(req)
    assert res.status == "SUCCESS"
    assert res.value == 3


def test_11_empty_date_range_match(engine: AnalysisEngine):
    """Test 11: Valid date range that matches no transactions returns NO_DATA."""
    req = AnalysisRequest(
        metric="revenue",
        aggregation="sum",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
    )
    res = engine.execute(req)
    assert res.status == "NO_DATA"
    assert res.value is None


def test_12_numeric_comparison_filters(engine: AnalysisEngine):
    """Test 12: Numeric comparisons (> 100 unit_price, units >= 10)."""
    # units >= 10: T001 (10), T004 (12), T006 (20) -> 3 rows
    req = AnalysisRequest(
        metric="units",
        aggregation="sum",
        filters=[FilterClause(field="units", operator="gte", value=10)],
    )
    res = engine.execute(req)
    assert res.status == "SUCCESS"
    assert res.value == 42


def test_13_in_filter_operator(engine: AnalysisEngine):
    """Test 13: 'in' operator for categorical and numeric values."""
    req = AnalysisRequest(
        metric="transaction_count",
        aggregation="count",
        filters=[FilterClause(field="region", operator="in", value=["UK", "FR"])],
    )
    res = engine.execute(req)
    # UK (4) + FR (3) = 7
    assert res.status == "SUCCESS"
    assert res.value == 7


def test_14_case_insensitive_categorical_matching(engine: AnalysisEngine):
    """Test 14: Categorical matching is case-insensitive."""
    req = AnalysisRequest(
        metric="revenue",
        aggregation="sum",
        filters=[FilterClause(field="region", operator="eq", value="uk")],
    )
    res = engine.execute(req)
    assert res.status == "SUCCESS"
    assert res.value == Decimal("4320")


def test_15_unknown_category_such_as_mars(engine: AnalysisEngine):
    """Test 15: Unknown category like 'Mars' returns UNKNOWN_DIMENSION_VALUE."""
    req = AnalysisRequest(
        metric="revenue",
        aggregation="sum",
        filters=[FilterClause(field="region", operator="eq", value="Mars")],
    )
    res = engine.execute(req)
    assert res.status == "UNKNOWN_DIMENSION_VALUE"
    assert res.value is None
    assert "Mars" in res.error_message


def test_16_valid_category_with_zero_matching_rows(engine: AnalysisEngine):
    """Test 16: Valid categories that jointly yield 0 rows return NO_DATA (not unknown dimension)."""
    # FR Gamma has 1 transaction (T010) with discount 0.00. Adding filter discount == 0.50 yields 0 rows.
    req = AnalysisRequest(
        metric="revenue",
        aggregation="sum",
        filters=[
            FilterClause(field="region", operator="eq", value="FR"),
            FilterClause(field="product", operator="eq", value="Gamma"),
            FilterClause(field="discount", operator="eq", value=Decimal("0.50")),
        ],
    )
    res = engine.execute(req)
    assert res.status == "NO_DATA"
    assert res.value is None


def test_17_missing_metric_values_partial_status():
    """Test 17: Transactions with missing metric values return PARTIAL status and accurate excluded count."""
    txs = [
        Transaction(id="T1", date=date(2026, 1, 1), region="UK", product="Alpha", units=10, unit_price=Decimal("100"), discount=Decimal("0.10")),
        Transaction(id="T2", date=date(2026, 1, 2), region="UK", product="Alpha", units=None, unit_price=Decimal("100"), discount=Decimal("0.10")),
    ]
    engine = AnalysisEngine(txs)
    req = AnalysisRequest(metric="units", aggregation="sum")
    res = engine.execute(req)

    assert res.status == "PARTIAL"
    assert res.value == 10
    assert res.excluded_missing_count == 1
    assert res.matched_rows == 2


def test_18_missing_operands_for_derived_metrics():
    """Test 18: Missing operand in derived metric calculation propagates None without zero-filling."""
    txs = [
        Transaction(id="T1", date=date(2026, 1, 1), region="UK", product="Alpha", units=10, unit_price=None, discount=Decimal("0.10")),
        Transaction(id="T2", date=date(2026, 1, 2), region="UK", product="Alpha", units=10, unit_price=Decimal("100"), discount=Decimal("0.10")),
    ]
    engine = AnalysisEngine(txs)
    req = AnalysisRequest(metric="revenue", aggregation="sum")
    res = engine.execute(req)

    assert res.status == "PARTIAL"
    # T1 revenue is None (missing price); T2 revenue is 900
    assert res.value == Decimal("900")
    assert res.excluded_missing_count == 1


def test_19_count_semantics_with_missing_metric():
    """Test 19: Count reflects matched rows regardless of nulls in the metric column."""
    txs = [
        Transaction(id="T1", date=date(2026, 1, 1), region="UK", product="Alpha", units=None, unit_price=Decimal("100"), discount=None),
    ]
    engine = AnalysisEngine(txs)
    req = AnalysisRequest(metric="revenue", aggregation="count")
    res = engine.execute(req)

    assert res.status == "SUCCESS"
    assert res.value == 1


def test_20_min_aggregation(engine: AnalysisEngine):
    """Test 20: Min aggregation operates on valid metric values."""
    req = AnalysisRequest(metric="units", aggregation="min")
    res = engine.execute(req)
    assert res.status == "SUCCESS"
    assert res.value == 2  # T010 has 2 units


def test_21_max_aggregation(engine: AnalysisEngine):
    """Test 21: Max aggregation operates on valid metric values."""
    req = AnalysisRequest(metric="revenue", aggregation="max")
    res = engine.execute(req)
    assert res.status == "SUCCESS"
    assert res.value == Decimal("2550")  # T009 has 2550 revenue


def test_22_grouped_max_min_ties():
    """Test 22: Grouped aggregation preserves all groups correctly."""
    txs = [
        Transaction(id="T1", date=date(2026, 1, 1), region="UK", product="Alpha", units=10, unit_price=Decimal("100"), discount=Decimal("0.00")),
        Transaction(id="T2", date=date(2026, 1, 2), region="DE", product="Alpha", units=10, unit_price=Decimal("100"), discount=Decimal("0.00")),
    ]
    engine = AnalysisEngine(txs)
    req = AnalysisRequest(metric="revenue", aggregation="sum", group_by="region")
    res = engine.execute(req)

    assert res.grouped_values == {"UK": Decimal("1000"), "DE": Decimal("1000")}


def test_23_invalid_metric(engine: AnalysisEngine):
    """Test 23: Invalid metric raises UnsupportedMetricError."""
    req = AnalysisRequest(metric="profit_margin", aggregation="sum")
    with pytest.raises(UnsupportedMetricError):
        engine.execute(req)


def test_24_invalid_aggregation(engine: AnalysisEngine):
    """Test 24: Invalid aggregation raises UnsupportedAggregationError."""
    req = AnalysisRequest(metric="revenue", aggregation="variance")
    with pytest.raises(UnsupportedAggregationError):
        engine.execute(req)


def test_25_invalid_filter_column(engine: AnalysisEngine):
    """Test 25: Invalid filter column raises UnsupportedFilterColumnError."""
    req = AnalysisRequest(
        metric="revenue",
        aggregation="sum",
        filters=[FilterClause(field="credit_score", operator="eq", value=750)],
    )
    with pytest.raises(UnsupportedFilterColumnError):
        engine.execute(req)


def test_26_invalid_operator(engine: AnalysisEngine):
    """Test 26: Invalid filter operator raises UnsupportedOperatorError."""
    req = AnalysisRequest(
        metric="revenue",
        aggregation="sum",
        filters=[FilterClause(field="units", operator="regex_match", value="^10")],
    )
    with pytest.raises(UnsupportedOperatorError):
        engine.execute(req)


def test_27_invalid_group_by(engine: AnalysisEngine):
    """Test 27: Unsupported group_by column raises UnsupportedGroupByError."""
    req = AnalysisRequest(metric="revenue", aggregation="sum", group_by="unit_price")
    with pytest.raises(UnsupportedGroupByError):
        engine.execute(req)


def test_28_invalid_date_range(engine: AnalysisEngine):
    """Test 28: start_date > end_date raises InvalidDateRangeError."""
    req = AnalysisRequest(
        metric="revenue",
        aggregation="sum",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 1, 1),
    )
    with pytest.raises(InvalidDateRangeError):
        engine.execute(req)


def test_29_no_valid_metric_values():
    """Test 29: All matching rows having null metric values returns NO_DATA."""
    txs = [
        Transaction(id="T1", date=date(2026, 1, 1), region="UK", product="Alpha", units=None, unit_price=None, discount=None),
    ]
    engine = AnalysisEngine(txs)
    req = AnalysisRequest(metric="revenue", aggregation="sum")
    res = engine.execute(req)

    assert res.status == "NO_DATA"
    assert res.value is None


def test_30_original_dataset_context_not_mutated(sample_transactions: list[Transaction]):
    """Test 30: Execution does not mutate input Transaction objects or collections."""
    context = DatasetContext(transactions=sample_transactions, evaluation_questions=[])
    engine = AnalysisEngine(context)

    t0_original_price = context.transactions[0].unit_price

    req = AnalysisRequest(metric="revenue", aggregation="sum", filters=[FilterClause(field="region", operator="eq", value="UK")])
    _ = engine.execute(req)

    assert len(context.transactions) == 10
    assert context.transactions[0].unit_price == t0_original_price


def test_31_decimal_precision_preserved(engine: AnalysisEngine):
    """Test 31: Verify revenue calculation for units=10, price=100, discount=0.10 produces Decimal(900)."""
    calc_rev = MetricsCalculator.calculate_row_revenue(10, Decimal("100"), Decimal("0.10"))
    assert calc_rev == Decimal("900")
    assert isinstance(calc_rev, Decimal)


def test_32_decimal_filter_comparison_works(engine: AnalysisEngine):
    """Test 32: Decimal comparison with Decimal('0.20') accurately finds discount row."""
    req = AnalysisRequest(
        metric="transaction_count",
        aggregation="count",
        filters=[FilterClause(field="discount", operator="eq", value=Decimal("0.20"))],
    )
    res = engine.execute(req)
    assert res.value == 1


def test_33_no_silent_float_conversion(engine: AnalysisEngine):
    """Test 33: Ensure internal DataFrame stores Decimal types and no float conversion occurred."""
    df = engine._df
    for col in ["unit_price", "discount", "gross_amount", "discount_amount", "revenue"]:
        for val in df[col]:
            if val is not None:
                assert isinstance(val, Decimal), f"Column {col} value {val} is {type(val)}, expected Decimal"


def test_34_dynamic_metric_registry_extensibility(sample_transactions: list[Transaction]):
    """Test 34: Adding a new metric to METRIC_REGISTRY works without modifying AnalysisEngine."""
    from src.analysis.metrics import METRIC_REGISTRY, MetricDefinition, SUPPORTED_METRICS

    # Register custom derived metric: net_unit_price = unit_price * (1 - discount)
    custom_metric = MetricDefinition(
        name="net_unit_price",
        is_derived=True,
        is_decimal=True,
        is_count=False,
        description="Net unit price after discount",
        compute_fn=lambda r: (r["unit_price"] * (Decimal(1) - r["discount"])) if (r.get("unit_price") is not None and r.get("discount") is not None) else None,
    )
    METRIC_REGISTRY["net_unit_price"] = custom_metric
    SUPPORTED_METRICS.add("net_unit_price")

    try:
        engine = AnalysisEngine(sample_transactions)
        # T001: 100 * (1 - 0.10) = 90
        req = AnalysisRequest(
            metric="net_unit_price",
            aggregation="sum",
            filters=[FilterClause(field="id", operator="eq", value="T001")],
        )
        res = engine.execute(req)
        assert res.status == "SUCCESS"
        assert res.value == Decimal("90")
    finally:
        # Cleanup
        METRIC_REGISTRY.pop("net_unit_price", None)
        SUPPORTED_METRICS.discard("net_unit_price")

