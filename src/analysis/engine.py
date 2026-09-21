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
    UnsupportedResultOperationError,
)
from src.analysis.metrics import (
    METRIC_REGISTRY,
    SUPPORTED_METRICS,
    MetricsCalculator,
)
from src.models import (
    ALLOWED_FILTER_OPERATORS,
    ALLOWED_GROUP_BY_COLUMNS,
    SUPPORTED_AGGREGATIONS,
    SUPPORTED_RESULT_OPERATIONS,
    AnalysisRequest,
    AnalysisResult,
    DatasetContext,
    FilterClause,
    OperationTrace,
    Transaction,
)

logger = logging.getLogger(__name__)

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
DECIMAL_COLUMNS: Set[str] = {
    "unit_price",
    "discount",
    "gross_amount",
    "discount_amount",
    "revenue",
}


def _is_valid(val: Any) -> bool:
    """Helper checking whether a value is non-null and not NaN."""
    if val is None:
        return False
    if isinstance(val, float) and pd.isna(val):
        return False
    return True


class AnalysisEngine:
    """Core deterministic analysis engine executing validated computations directly on records."""

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
        """Validates request, filters dataset, executes aggregation, and returns structured AnalysisResult."""
        logger.info(
            "Analysis started: metric=%s, aggregation=%s, group_by=%s, result_operation=%s, filters_count=%d",
            request.metric,
            request.aggregation,
            request.group_by,
            request.result_operation,
            len(request.filters),
        )

        # 1. Structural and Domain Validation
        self._validate_request(request)

        # 2. Check for unknown categorical filter dimension values
        unknown_dim_result = self._check_dimension_values(request)
        if unknown_dim_result is not None:
            logger.info("Analysis completed with UNKNOWN_DIMENSION_VALUE: %s", unknown_dim_result.error_message)
            return unknown_dim_result

        # 3. Apply Filter Clauses
        filtered_df, filter_traces = self._apply_filters(request)

        # 4. Check for Empty Dataset (NO_DATA)
        if filtered_df.empty:
            logger.info("Analysis completed: NO_DATA matching filter criteria")
            return AnalysisResult(
                status="NO_DATA",
                metric=request.metric,
                aggregation=request.aggregation,
                group_by=request.group_by,
                result_operation=request.result_operation,
                value=None,
                grouped_values={},
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
            "Analysis completed: status=%s, matched_rows=%d, value=%s, selected_group=%s",
            result.status,
            result.matched_rows,
            result.value if not result.grouped_values else result.grouped_values,
            result.selected_group,
        )
        return result

    def _validate_request(self, request: AnalysisRequest) -> None:
        """Validates metric, aggregation, group_by, result_operation, filter columns, operators, and date ranges."""
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

        if request.result_operation is not None:
            if request.result_operation not in SUPPORTED_RESULT_OPERATIONS:
                raise UnsupportedResultOperationError(
                    f"Unsupported result_operation '{request.result_operation}'. Allowed: {sorted(SUPPORTED_RESULT_OPERATIONS)}"
                )
            if request.group_by is None:
                raise InvalidRequestError("result_operation requires group_by to be specified.")

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
                            result_operation=request.result_operation,
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
                            result_operation=request.result_operation,
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
        """Evaluates a single FilterClause against the internal DataFrame."""
        series = self._df[f.field]
        val = f.value
        op = f.operator

        # Normalize categorical strings (case-insensitive)
        if f.field in ("region", "product", "id"):
            series_lower = series.apply(lambda x: str(x).strip().lower() if x is not None else "")
            if op == "eq":
                target_lower = str(val).strip().lower()
                return series_lower == target_lower, f"{f.field} == '{val}'"
            elif op == "neq":
                target_lower = str(val).strip().lower()
                return (series_lower != target_lower) & series.notna(), f"{f.field} != '{val}'"
            elif op == "in":
                target_list_lower = [str(v).strip().lower() for v in (val if isinstance(val, (list, tuple, set)) else [val])]
                return series_lower.isin(target_list_lower), f"{f.field} in {val}"
            else:
                raise UnsupportedOperatorError(f"Operator '{op}' not supported for categorical column '{f.field}'")

        # Normalize numeric Decimals
        if f.field in DECIMAL_COLUMNS:
            try:
                if op == "between":
                    d1 = Decimal(str(val[0]))
                    d2 = Decimal(str(val[1]))
                    mask = series.apply(lambda x: d1 <= x <= d2 if x is not None else False)
                    return mask, f"{d1} <= {f.field} <= {d2}"
                elif op == "in":
                    dec_list = [Decimal(str(v)) for v in val]
                    mask = series.apply(lambda x: x in dec_list if x is not None else False)
                    return mask, f"{f.field} in {dec_list}"
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
                        raise UnsupportedOperatorError(f"Operator '{op}' not supported for column '{f.field}'")
                    return mask, f"{f.field} {op} {target}"
            except (InvalidOperation, TypeError, ValueError) as e:
                raise InvalidFilterValueError(f"Invalid decimal filter value '{val}' for '{f.field}': {e}") from e

        # Normalize units (integer)
        if f.field == "units":
            try:
                if op == "between":
                    i1 = int(val[0])
                    i2 = int(val[1])
                    mask = series.apply(lambda x: i1 <= x <= i2 if x is not None else False)
                    return mask, f"{i1} <= units <= {i2}"
                elif op == "in":
                    int_list = [int(v) for v in val]
                    mask = series.apply(lambda x: x in int_list if x is not None else False)
                    return mask, f"units in {int_list}"
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
                explanation="All matching records contained null values for this metric.",
            )

        metric_def = MetricsCalculator.get_definition(request.metric)
        calculated_value = self._compute_aggregate(
            valid_values, request.aggregation, metric_def.is_decimal
        )

        status = "PARTIAL" if excluded_missing > 0 else "SUCCESS"

        return AnalysisResult(
            status=status,
            metric=request.metric,
            aggregation=request.aggregation,
            value=calculated_value,
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

        # Execute result_operation (highest/lowest) selection if requested
        selected_group: Optional[str] = None
        selected_value: Any = None

        if request.result_operation:
            valid_groups = {k: v for k, v in grouped_values.items() if v is not None}
            if valid_groups:
                sorted_keys = sorted(valid_groups.keys())
                if request.result_operation == "highest":
                    selected_group = max(sorted_keys, key=lambda k: valid_groups[k])
                    selected_value = valid_groups[selected_group]
                elif request.result_operation == "lowest":
                    selected_group = min(sorted_keys, key=lambda k: valid_groups[k])
                    selected_value = valid_groups[selected_group]

        status = "PARTIAL" if total_excluded_missing > 0 else "SUCCESS"

        return AnalysisResult(
            status=status,
            metric=request.metric,
            aggregation=request.aggregation,
            value=selected_value,
            grouped_values=grouped_values,
            group_by=group_col,
            result_operation=request.result_operation,
            selected_group=selected_group,
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
