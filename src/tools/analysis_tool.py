"""Analysis tool bridging dictionary-based tool invocations to the deterministic AnalysisEngine."""

from datetime import date
import logging
from typing import Any, Dict, List, Optional

from src.analysis.engine import AnalysisEngine
from src.analysis.exceptions import InvalidRequestError
from src.models import AnalysisRequest, AnalysisResult, FilterClause

logger = logging.getLogger(__name__)


class AnalysisTool:
    """Tool wrapper translating incoming dictionary parameters into structured AnalysisRequest objects."""

    name: str = "run_analysis"
    description: str = (
        "Executes deterministic data analysis over validated transaction records "
        "supporting filtering, date ranges, metrics, aggregations, and grouping."
    )

    def __init__(self, engine: AnalysisEngine) -> None:
        self.engine: AnalysisEngine = engine

    def run(self, **kwargs: Any) -> AnalysisResult:
        """Parses arguments, normalizes filter structures, and executes analysis via the engine."""
        logger.info("AnalysisTool.run invoked with arguments: %s", list(kwargs.keys()))

        metric = kwargs.get("metric")
        aggregation = kwargs.get("aggregation")

        if not metric or not isinstance(metric, str):
            return AnalysisResult(
                status="INVALID_REQUEST",
                error_message="Missing required argument 'metric' (must be a non-empty string).",
                explanation="Missing required argument 'metric'.",
            )

        if not aggregation or not isinstance(aggregation, str):
            return AnalysisResult(
                status="INVALID_REQUEST",
                metric=str(metric) if metric else None,
                error_message="Missing required argument 'aggregation' (must be a non-empty string).",
                explanation="Missing required argument 'aggregation'.",
            )

        # 1. Parse and normalize filter clauses
        raw_filters = kwargs.get("filters", [])
        parsed_filters: List[FilterClause] = []
        if raw_filters:
            if not isinstance(raw_filters, list):
                return AnalysisResult(
                    status="INVALID_REQUEST",
                    metric=metric,
                    aggregation=aggregation,
                    error_message="Argument 'filters' must be a list of filter clause objects.",
                    explanation="Argument 'filters' must be a list.",
                )
            for idx, f in enumerate(raw_filters):
                if isinstance(f, FilterClause):
                    parsed_filters.append(f)
                elif isinstance(f, dict):
                    if "field" not in f or "operator" not in f or "value" not in f:
                        return AnalysisResult(
                            status="INVALID_REQUEST",
                            metric=metric,
                            aggregation=aggregation,
                            error_message=(
                                f"Filter at index {idx} must contain 'field', 'operator', and 'value' keys."
                            ),
                            explanation=f"Malformed filter dictionary at index {idx}.",
                        )
                    parsed_filters.append(
                        FilterClause(
                            field=str(f["field"]),
                            operator=str(f["operator"]),
                            value=f["value"],
                        )
                    )
                else:
                    return AnalysisResult(
                        status="INVALID_REQUEST",
                        metric=metric,
                        aggregation=aggregation,
                        error_message=f"Filter at index {idx} must be a dictionary or FilterClause object.",
                        explanation=f"Invalid filter type at index {idx}.",
                    )

        # 2. Parse optional date range
        raw_start_date = kwargs.get("start_date")
        start_date_obj: Optional[date] = None
        if raw_start_date:
            if isinstance(raw_start_date, date):
                start_date_obj = raw_start_date
            elif isinstance(raw_start_date, str):
                try:
                    start_date_obj = date.fromisoformat(raw_start_date.strip())
                except ValueError as e:
                    return AnalysisResult(
                        status="INVALID_REQUEST",
                        metric=metric,
                        aggregation=aggregation,
                        error_message=f"Invalid start_date format '{raw_start_date}'. Expected YYYY-MM-DD: {e}",
                        explanation="Invalid start_date format.",
                    )
            else:
                return AnalysisResult(
                    status="INVALID_REQUEST",
                    metric=metric,
                    aggregation=aggregation,
                    error_message=f"start_date must be a string (YYYY-MM-DD) or date object, got {type(raw_start_date).__name__}",
                )

        raw_end_date = kwargs.get("end_date")
        end_date_obj: Optional[date] = None
        if raw_end_date:
            if isinstance(raw_end_date, date):
                end_date_obj = raw_end_date
            elif isinstance(raw_end_date, str):
                try:
                    end_date_obj = date.fromisoformat(raw_end_date.strip())
                except ValueError as e:
                    return AnalysisResult(
                        status="INVALID_REQUEST",
                        metric=metric,
                        aggregation=aggregation,
                        error_message=f"Invalid end_date format '{raw_end_date}'. Expected YYYY-MM-DD: {e}",
                        explanation="Invalid end_date format.",
                    )
            else:
                return AnalysisResult(
                    status="INVALID_REQUEST",
                    metric=metric,
                    aggregation=aggregation,
                    error_message=f"end_date must be a string (YYYY-MM-DD) or date object, got {type(raw_end_date).__name__}",
                )

        # 3. Parse optional group_by
        group_by = kwargs.get("group_by")
        if group_by is not None and not isinstance(group_by, str):
            return AnalysisResult(
                status="INVALID_REQUEST",
                metric=metric,
                aggregation=aggregation,
                error_message=f"group_by must be a string, got {type(group_by).__name__}",
            )

        # 4. Construct request and delegate to AnalysisEngine
        request = AnalysisRequest(
            metric=metric,
            aggregation=aggregation,
            filters=parsed_filters,
            start_date=start_date_obj,
            end_date=end_date_obj,
            group_by=group_by,
        )

        try:
            return self.engine.execute(request)
        except InvalidRequestError as e:
            logger.warning("AnalysisEngine rejected request with domain error: %s", e)
            return AnalysisResult(
                status="INVALID_REQUEST",
                metric=metric,
                aggregation=aggregation,
                group_by=group_by,
                error_message=str(e),
                explanation=str(e),
            )
