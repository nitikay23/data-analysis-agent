"""Presentation formatter applying authoritative domain formatting rules."""

from decimal import Decimal, ROUND_HALF_UP
import logging
from typing import Any, Dict, Optional, Union

from src.analysis.metrics import METRIC_REGISTRY
from src.models import AnalysisResult

logger = logging.getLogger(__name__)


class PresentationFormatter:
    """Formats deterministic analysis results for user display without altering underlying values.

    Presentation-only component: does not perform calculations, max/min reductions, or business logic.
    """

    @staticmethod
    def format_number(val: Union[int, float, Decimal], metric_name: Optional[str] = None) -> str:
        """Formats numbers according to authoritative metric metadata."""
        if val is None:
            return "N/A"

        metric_def = METRIC_REGISTRY.get(metric_name) if metric_name else None

        # 1. Percentage metric (e.g. discount)
        if metric_name == "discount":
            if isinstance(val, (int, float, Decimal)):
                dec_val = Decimal(str(val))
                pct = (dec_val * Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if pct == pct.to_integral():
                    return f"{int(pct)}%"
                return f"{pct:.2f}%"

        # 2. Integer count metrics (e.g. transaction_count)
        if metric_def and metric_def.is_count:
            return str(int(val))

        if isinstance(val, int):
            return str(val)

        # 3. Units metric whole numbers
        if metric_def and metric_def.name == "units":
            if isinstance(val, Decimal) and val == val.to_integral():
                return str(int(val))
            if isinstance(val, float) and val.is_integer():
                return str(int(val))

        # 4. Continuous / Monetary / Decimal metrics & averages
        if isinstance(val, Decimal):
            dec_val = val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return f"{dec_val:.2f}"

        if isinstance(val, float):
            dec_val = Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return f"{dec_val:.2f}"

        return str(val)

    @classmethod
    def format_result(cls, result: AnalysisResult, metric_name: Optional[str] = None) -> str:
        """Formats an AnalysisResult into an exact grounded string response."""
        effective_metric = metric_name or result.metric or ""

        if result.status == "NO_DATA":
            return "No matching records found for the specified query."

        if result.status == "UNKNOWN_DIMENSION_VALUE":
            detail = result.error_message or result.explanation or "Unknown dimension value."
            return f"Unknown dimension value: {detail}"

        if result.status == "INVALID_REQUEST":
            detail = result.error_message or result.explanation or "Invalid analysis request."
            return f"Invalid request: {detail}"

        # 1. Comparative / Selected group natural language response
        if result.selected_group is not None:
            formatted_val = cls.format_number(result.value, effective_metric)
            group_label = result.group_by or "group"
            op_label = result.result_operation or "selected"
            if result.aggregation == "sum":
                agg_label = "total "
            elif result.aggregation and result.aggregation != "none":
                agg_label = f"{result.aggregation} "
            else:
                agg_label = ""

            output_str = f"The {group_label} with the {op_label} {agg_label}{effective_metric} is {result.selected_group}, with {formatted_val}."
            if result.status == "PARTIAL":
                output_str += f" (Note: {result.excluded_missing_count} records were excluded due to missing values)"
            return output_str

        # 2. Standard grouped values handling: formats all grouped entries
        if result.grouped_values is not None:
            formatted_groups = []
            for group_key in sorted(result.grouped_values.keys()):
                group_val = result.grouped_values[group_key]
                formatted_val = cls.format_number(group_val, effective_metric)
                formatted_groups.append(f"{group_key}: {formatted_val}")

            output_str = ", ".join(formatted_groups)
            if result.status == "PARTIAL":
                output_str += f" (Note: {result.excluded_missing_count} records were excluded due to missing values)"
            return output_str

        # 3. Scalar value handling
        formatted_val = cls.format_number(result.value, effective_metric)
        if result.status == "PARTIAL":
            return f"{formatted_val} (Note: {result.excluded_missing_count} records were excluded due to missing values)"

        return formatted_val
