"""Deterministic analysis engine for filtering, aggregation, and grouping."""

from datetime import date
from decimal import Decimal, InvalidOperation
import logging
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

import pandas as pd

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
    MetricsCalculator,
)
from src.models import (
    AnalysisRequest,
    AnalysisResult,
    DatasetContext,
    FilterClause,
    OperationTrace,
    Transaction,
)

logger = logging.getLogger(__name__)

SUPPORTED_AGGREGATIONS: Set[str] = {"sum", "count", "mean", "median", "min", "max"}
ALLOWED_FILTER_COLUMNS: Set[str] = {
    "id",
    "date",
    "region",
    "product",
    "units",
    "unit_price",
    "discount",
    "gross_amount",
    "discount_amount",
    "revenue",
}
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
ALLOWED_GROUP_BY_COLUMNS: Set[str] = {"region", "product"}
DECIMAL_COLUMNS: Set[str] = {
    "unit_price",
    "discount",
    "gross_amount",
    "discount_amount",
    "revenue",
}


def _is_valid(val: Any) -> bool:
    """Returns True if value is not None and not NaN."""
    if val is None:
        return False
    try:
        if pd.isna(val):
            return False
    except (ValueError, TypeError):
        pass
    return True


class AnalysisEngine:
    """Performs deterministic dataset queries, arithmetic calculations, and aggregations."""

    def __init__(self, dataset: Union[List[Transaction], DatasetContext]) -> None:
        if isinstance(dataset, DatasetContext):
            self.transactions: List[Transaction] = dataset.transactions
        elif isinstance(dataset, list):
            self.transactions = dataset
        else:
            raise TypeError(f"Expected List[Transaction] or DatasetContext, got {type(dataset).__name__}")

        # Build internal pandas DataFrame representation preserving Python Decimal objects
        self._df: pd.DataFrame = self._build_internal_dataframe(self.transactions)

        # Cache known categorical domains directly from trusted transactions
        self._known_regions: Set[str] = {t.region for t in self.transactions if t.region}
        self._known_products: Set[str] = {t.product for t in self.transactions if t.product}

    def _build_internal_dataframe(self, transactions: List[Transaction]) -> pd.DataFrame:
        """Constructs an internal pandas DataFrame from trusted transactions without float conversions."""
        records = []
        for t in transactions:
            row: Dict[str, Any] = {
                "id": t.id,
                "date": t.date,
                "region": t.region,
                "product": t.product,
                "units": t.units,
                "unit_price": t.unit_price,
                "discount": t.discount,
            }
            # Dynamically compute all registered derived metrics
            for m_name, m_def in METRIC_REGISTRY.items():
                if m_def.is_derived and m_def.compute_fn is not None:
                    row[m_name] = m_def.compute_fn(row)
            records.append(row)

        if not records:
            columns = [
                "id",
                "date",
                "region",
                "product",
                "units",
                "unit_price",
                "discount",
            ] + [m_name for m_name, m_def in METRIC_REGISTRY.items() if m_def.is_derived]
            return pd.DataFrame(columns=columns)

        df = pd.DataFrame(records)
        df["units"] = df["units"].astype(object)
        # Ensure Decimal columns are explicitly stored as object dtype to avoid float conversion
        for col in DECIMAL_COLUMNS:
            if col in df.columns:
                df[col] = df[col].astype(object)
        return df



    def execute(self, request: AnalysisRequest) -> AnalysisResult:
        """Executes a structured analytical request deterministically."""
        logger.info(
            "Analysis started: metric=%s, aggregation=%s, group_by=%s, filters_count=%d",
            request.metric,
            request.aggregation,
            request.group_by,
            len(request.filters),
        )

        # 1. Structural request validation
        self._validate_request(request)

        # 2. Check for unknown dimension values (distinguishing from NO_DATA)
        unknown_dim_result = self._check_dimension_values(request)
        if unknown_dim_result is not None:
            logger.info(
                "Analysis completed with UNKNOWN_DIMENSION_VALUE: %s",
                unknown_dim_result.error_message,
            )
            return unknown_dim_result

        # 3. Apply filters and date range
        filtered_df, filter_traces = self._apply_filters(request)
        matched_rows = len(filtered_df)

        # 4. Handle zero matching records
        if matched_rows == 0:
            logger.info("Analysis completed with NO_DATA (0 rows matched)")
            if request.aggregation == "count" or request.metric == "transaction_count":
                return AnalysisResult(
                    status="SUCCESS",
                    metric=request.metric,
                    aggregation=request.aggregation,
                    value=0,
                    grouped_values={} if request.group_by else None,
                    group_by=request.group_by,
                    matched_rows=0,
                    excluded_missing_count=0,
                    total_matching_records=0,
                    trace=OperationTrace(
                        filters_applied=filter_traces,
                        date_range_applied=self._format_date_range(request),
                        metric=request.metric,
                        aggregation=request.aggregation,
                        group_by=request.group_by,
                        matched_rows=0,
                        excluded_rows=0,
                        calculation_details="0 matching records",
                    ),
                    explanation="No records matched the filter criteria.",
                )
            return AnalysisResult(
                status="NO_DATA",
                metric=request.metric,
                aggregation=request.aggregation,
                value=None,
                grouped_values=None,
                group_by=request.group_by,
                matched_rows=0,
                excluded_missing_count=0,
                total_matching_records=0,
                trace=OperationTrace(
                    filters_applied=filter_traces,
                    date_range_applied=self._format_date_range(request),
                    metric=request.metric,
                    aggregation=request.aggregation,
                    group_by=request.group_by,
                    matched_rows=0,
                    excluded_rows=0,
                    calculation_details="0 matching records",
                ),
                explanation="No records matched the filter criteria.",
            )

        # 5. Execute aggregation (Grouped or Scalar)
        if request.group_by:
            result = self._execute_grouped_aggregation(
                filtered_df, request, filter_traces
            )
        else:
            result = self._execute_scalar_aggregation(
                filtered_df, request, filter_traces
            )

        logger.info(
            "Analysis completed: status=%s, matched_rows=%d, value=%s",
            result.status,
            result.matched_rows,
            result.value if not result.grouped_values else result.grouped_values,
        )
        return result

    def _validate_request(self, request: AnalysisRequest) -> None:
        """Validates metric, aggregation, group_by, filter columns, operators, and date ranges."""
        if not MetricsCalculator.is_supported(request.metric):
            raise UnsupportedMetricError(
                f"Unsupported metric '{request.metric}'. Allowed metrics: {sorted(SUPPORTED_METRICS)}"
            )

        if request.aggregation not in SUPPORTED_AGGREGATIONS:
            raise UnsupportedAggregationError(
                f"Unsupported aggregation '{request.aggregation}'. Allowed aggregations: {sorted(SUPPORTED_AGGREGATIONS)}"
            )

        if request.group_by is not None and request.group_by not in ALLOWED_GROUP_BY_COLUMNS:
            raise UnsupportedGroupByError(
                f"Unsupported group_by column '{request.group_by}'. Allowed: {sorted(ALLOWED_GROUP_BY_COLUMNS)}"
            )

        if request.start_date and request.end_date and request.start_date > request.end_date:
            raise InvalidDateRangeError(
                f"Invalid date range: start_date '{request.start_date}' cannot be after end_date '{request.end_date}'."
            )

        for f in request.filters:
            if f.field not in ALLOWED_FILTER_COLUMNS:
                raise UnsupportedFilterColumnError(
                    f"Unsupported filter column '{f.field}'. Allowed: {sorted(ALLOWED_FILTER_COLUMNS)}"
                )
            if f.operator not in ALLOWED_FILTER_OPERATORS:
                raise UnsupportedOperatorError(
                    f"Unsupported filter operator '{f.operator}'. Allowed: {sorted(ALLOWED_FILTER_OPERATORS)}"
                )

    def _check_dimension_values(self, request: AnalysisRequest) -> Optional[AnalysisResult]:
        """Validates that categorical filter values exist in trusted domain values."""
        for f in request.filters:
            if f.field == "region":
                vals = f.value if isinstance(f.value, (list, tuple, set)) else [f.value]
                for val in vals:
                    if str(val).strip().lower() not in {r.lower() for r in self._known_regions}:
                        return AnalysisResult(
                            status="UNKNOWN_DIMENSION_VALUE",
                            metric=request.metric,
                            aggregation=request.aggregation,
                            group_by=request.group_by,
                            value=None,
                            explanation=f"Unknown region '{val}'. Known regions: {sorted(self._known_regions)}",
                            error_message=f"Unknown region '{val}'",
                        )

            elif f.field == "product":
                vals = f.value if isinstance(f.value, (list, tuple, set)) else [f.value]
                for val in vals:
                    if str(val).strip().lower() not in {p.lower() for p in self._known_products}:
                        return AnalysisResult(
                            status="UNKNOWN_DIMENSION_VALUE",
                            metric=request.metric,
                            aggregation=request.aggregation,
                            group_by=request.group_by,
                            value=None,
                            explanation=f"Unknown product '{val}'. Known products: {sorted(self._known_products)}",
                            error_message=f"Unknown product '{val}'",
                        )
        return None

    def _apply_filters(self, request: AnalysisRequest) -> Tuple[pd.DataFrame, List[str]]:
        """Applies filter clauses and date ranges to the DataFrame."""
        if self._df.empty:
            return self._df.copy(), []

        mask = pd.Series(True, index=self._df.index)
        filter_traces: List[str] = []

        for f in request.filters:
            clause_mask, trace_str = self._evaluate_filter_clause(f)
            mask &= clause_mask
            filter_traces.append(trace_str)

        # Date range filtering (inclusive)
        if request.start_date:
            mask &= self._df["date"] >= request.start_date
            filter_traces.append(f"date >= {request.start_date}")
        if request.end_date:
            mask &= self._df["date"] <= request.end_date
            filter_traces.append(f"date <= {request.end_date}")

        return self._df[mask].copy(), filter_traces

    def _evaluate_filter_clause(self, f: FilterClause) -> Tuple[pd.Series, str]:
        """Evaluates a single filter clause returning a boolean Series mask."""
        series = self._df[f.field]
        op = f.operator
        val = f.value

        # Normalize comparison values for categorical string fields (case-insensitive)
        if f.field in {"region", "product", "id"}:
            if op == "eq":
                target = str(val).strip().lower()
                mask = series.astype(str).str.strip().str.lower() == target
                return mask, f"{f.field} == '{val}'"
            elif op == "neq":
                target = str(val).strip().lower()
                mask = series.astype(str).str.strip().str.lower() != target
                return mask, f"{f.field} != '{val}'"
            elif op == "in":
                targets = {str(v).strip().lower() for v in val}
                mask = series.astype(str).str.strip().str.lower().isin(targets)
                return mask, f"{f.field} in {val}"
            else:
                raise UnsupportedOperatorError(f"Operator '{op}' is not supported for text column '{f.field}'")

        # Normalize comparison values for Decimal columns
        if f.field in DECIMAL_COLUMNS:
            try:
                if op == "between":
                    if not isinstance(val, (list, tuple)) or len(val) != 2:
                        raise InvalidFilterValueError(f"'between' operator requires a 2-element sequence, got {val}")
                    target_low = Decimal(str(val[0]))
                    target_high = Decimal(str(val[1]))
                    mask = series.apply(
                        lambda x: (x is not None and target_low <= x <= target_high)
                    )
                    return mask, f"{target_low} <= {f.field} <= {target_high}"
                elif op == "in":
                    targets = {Decimal(str(v)) for v in val}
                    mask = series.apply(lambda x: x in targets if x is not None else False)
                    return mask, f"{f.field} in {[str(t) for t in targets]}"
                else:
                    target = Decimal(str(val))
                    if op == "eq":
                        mask = series.apply(lambda x: x == target if x is not None else False)
                    elif op == "neq":
                        mask = series.apply(lambda x: x != target if x is not None else False)
                    elif op == "gt":
                        mask = series.apply(lambda x: x > target if x is not None else False)
                    elif op == "gte":
                        mask = series.apply(lambda x: x >= target if x is not None else False)
                    elif op == "lt":
                        mask = series.apply(lambda x: x < target if x is not None else False)
                    elif op == "lte":
                        mask = series.apply(lambda x: x <= target if x is not None else False)
                    else:
                        raise UnsupportedOperatorError(f"Operator '{op}' not supported for numeric column '{f.field}'")
                    return mask, f"{f.field} {op} {target}"
            except (InvalidOperation, TypeError, ValueError) as e:
                raise InvalidFilterValueError(
                    f"Invalid Decimal filter value '{val}' for column '{f.field}': {e}"
                ) from e

        # Normalize units (integer)
        if f.field == "units":
            try:
                if op == "between":
                    target_low = int(val[0])
                    target_high = int(val[1])
                    mask = series.apply(
                        lambda x: (x is not None and target_low <= x <= target_high)
                    )
                    return mask, f"{target_low} <= units <= {target_high}"
                elif op == "in":
                    targets = {int(v) for v in val}
                    mask = series.apply(lambda x: x in targets if x is not None else False)
                    return mask, f"units in {targets}"
                else:
                    target = int(val)
                    if op == "eq":
                        mask = series.apply(lambda x: x == target if x is not None else False)
                    elif op == "neq":
                        mask = series.apply(lambda x: x != target if x is not None else False)
                    elif op == "gt":
                        mask = series.apply(lambda x: x > target if x is not None else False)
                    elif op == "gte":
                        mask = series.apply(lambda x: x >= target if x is not None else False)
                    elif op == "lt":
                        mask = series.apply(lambda x: x < target if x is not None else False)
                    elif op == "lte":
                        mask = series.apply(lambda x: x <= target if x is not None else False)
                    else:
                        raise UnsupportedOperatorError(f"Operator '{op}' not supported for column 'units'")
                    return mask, f"units {op} {target}"
            except (TypeError, ValueError) as e:
                raise InvalidFilterValueError(f"Invalid integer filter value '{val}' for 'units': {e}") from e

        # Normalize date
        if f.field == "date":
            try:
                if op == "between":
                    d1 = val[0] if isinstance(val[0], date) else date.fromisoformat(str(val[0]))
                    d2 = val[1] if isinstance(val[1], date) else date.fromisoformat(str(val[1]))
                    mask = (series >= d1) & (series <= d2)
                    return mask, f"{d1} <= date <= {d2}"
                else:
                    target_date = val if isinstance(val, date) else date.fromisoformat(str(val))
                    if op == "eq":
                        mask = series == target_date
                    elif op == "neq":
                        mask = series != target_date
                    elif op == "gt":
                        mask = series > target_date
                    elif op == "gte":
                        mask = series >= target_date
                    elif op == "lt":
                        mask = series < target_date
                    elif op == "lte":
                        mask = series <= target_date
                    else:
                        raise UnsupportedOperatorError(f"Operator '{op}' not supported for column 'date'")
                    return mask, f"date {op} {target_date}"
            except (ValueError, TypeError) as e:
                raise InvalidFilterValueError(f"Invalid date filter value '{val}': {e}") from e

        raise UnsupportedFilterColumnError(f"Filter column '{f.field}' not supported")

    def _execute_scalar_aggregation(
        self,
        df: pd.DataFrame,
        request: AnalysisRequest,
        filter_traces: List[str],
    ) -> AnalysisResult:
        """Computes a single scalar aggregate across all matching rows."""
        matched_rows = len(df)

        if request.aggregation == "count" or request.metric == "transaction_count":
            return AnalysisResult(
                status="SUCCESS",
                metric=request.metric,
                aggregation="count",
                value=matched_rows,
                matched_rows=matched_rows,
                excluded_missing_count=0,
                total_matching_records=matched_rows,
                trace=OperationTrace(
                    filters_applied=filter_traces,
                    date_range_applied=self._format_date_range(request),
                    metric=request.metric,
                    aggregation="count",
                    matched_rows=matched_rows,
                    excluded_rows=0,
                    calculation_details=f"count({matched_rows} records)",
                ),
            )

        # Extract non-null metric values
        raw_series = df[request.metric]
        valid_values: List[Any] = [v for v in raw_series if _is_valid(v)]
        excluded_missing = matched_rows - len(valid_values)

        if not valid_values:
            return AnalysisResult(
                status="NO_DATA",
                metric=request.metric,
                aggregation=request.aggregation,
                value=None,
                matched_rows=matched_rows,
                excluded_missing_count=excluded_missing,
                total_matching_records=matched_rows,
                trace=OperationTrace(
                    filters_applied=filter_traces,
                    date_range_applied=self._format_date_range(request),
                    metric=request.metric,
                    aggregation=request.aggregation,
                    matched_rows=matched_rows,
                    excluded_rows=excluded_missing,
                    calculation_details="All matching records contained missing values for metric.",
                ),
                explanation=f"All {matched_rows} matching records have missing values for metric '{request.metric}'.",
            )

        metric_def = MetricsCalculator.get_definition(request.metric)
        computed_val = self._compute_aggregate(valid_values, request.aggregation, metric_def.is_decimal)
        status = "PARTIAL" if excluded_missing > 0 else "SUCCESS"

        return AnalysisResult(
            status=status,
            metric=request.metric,
            aggregation=request.aggregation,
            value=computed_val,
            matched_rows=matched_rows,
            excluded_missing_count=excluded_missing,
            total_matching_records=matched_rows,
            trace=OperationTrace(
                filters_applied=filter_traces,
                date_range_applied=self._format_date_range(request),
                metric=request.metric,
                aggregation=request.aggregation,
                matched_rows=matched_rows,
                excluded_rows=excluded_missing,
                calculation_details=f"{request.aggregation}({len(valid_values)} valid values)",
            ),
        )

    def _execute_grouped_aggregation(
        self,
        df: pd.DataFrame,
        request: AnalysisRequest,
        filter_traces: List[str],
    ) -> AnalysisResult:
        """Computes aggregation grouped by a categorical column (region or product)."""
        group_col = request.group_by
        assert group_col is not None

        matched_rows = len(df)
        grouped_values: Dict[str, Any] = {}
        total_excluded_missing = 0
        metric_def = MetricsCalculator.get_definition(request.metric)

        for group_name, sub_df in df.groupby(group_col):
            str_group_name = str(group_name)
            if request.aggregation == "count" or request.metric == "transaction_count":
                grouped_values[str_group_name] = len(sub_df)
            else:
                valid_vals = [v for v in sub_df[request.metric] if _is_valid(v)]
                total_excluded_missing += (len(sub_df) - len(valid_vals))
                if not valid_vals:
                    grouped_values[str_group_name] = None
                else:
                    grouped_values[str_group_name] = self._compute_aggregate(
                        valid_vals, request.aggregation, metric_def.is_decimal
                    )


        status = "PARTIAL" if total_excluded_missing > 0 else "SUCCESS"

        return AnalysisResult(
            status=status,
            metric=request.metric,
            aggregation=request.aggregation,
            grouped_values=grouped_values,
            group_by=group_col,
            matched_rows=matched_rows,
            excluded_missing_count=total_excluded_missing,
            total_matching_records=matched_rows,
            trace=OperationTrace(
                filters_applied=filter_traces,
                date_range_applied=self._format_date_range(request),
                metric=request.metric,
                aggregation=request.aggregation,
                group_by=group_col,
                matched_rows=matched_rows,
                excluded_rows=total_excluded_missing,
                calculation_details=f"Grouped by {group_col}: {len(grouped_values)} groups computed",
            ),
        )

    def _compute_aggregate(
        self,
        values: Sequence[Any],
        aggregation: str,
        is_decimal: bool,
    ) -> Any:
        """Executes the exact mathematical aggregation (sum, mean, median, min, max)."""
        n = len(values)
        if n == 0:
            return None

        if aggregation == "sum":
            if is_decimal:
                return sum(values, Decimal(0))
            return sum(values)

        elif aggregation == "mean":
            if is_decimal:
                total = sum(values, Decimal(0))
                return total / Decimal(n)
            return sum(values) / n

        elif aggregation == "median":
            sorted_vals = sorted(values)
            mid = n // 2
            if n % 2 == 1:
                return sorted_vals[mid]
            else:
                if is_decimal:
                    return (sorted_vals[mid - 1] + sorted_vals[mid]) / Decimal(2)
                return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2

        elif aggregation == "min":
            return min(values)

        elif aggregation == "max":
            return max(values)

        raise UnsupportedAggregationError(f"Unsupported aggregation '{aggregation}'")

    @staticmethod
    def _format_date_range(request: AnalysisRequest) -> Optional[str]:
        if request.start_date or request.end_date:
            return f"{request.start_date or 'START'} to {request.end_date or 'END'}"
        return None
