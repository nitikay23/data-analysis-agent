"""Custom exceptions for the deterministic analysis engine."""


class AnalysisError(Exception):
    """Base exception for analysis engine errors."""
    pass


class InvalidRequestError(AnalysisError, ValueError):
    """Raised when an analysis request specification is invalid or unsupported."""
    pass


class UnsupportedMetricError(InvalidRequestError):
    """Raised when a requested metric is not supported by the metric registry."""
    pass


class UnsupportedAggregationError(InvalidRequestError):
    """Raised when a requested aggregation is not supported."""
    pass


class UnsupportedFilterColumnError(InvalidRequestError):
    """Raised when a filter column is not allowed."""
    pass


class UnsupportedOperatorError(InvalidRequestError):
    """Raised when a filter operator is not supported."""
    pass


class UnsupportedGroupByError(InvalidRequestError):
    """Raised when a group_by column is not supported."""
    pass


class InvalidFilterValueError(InvalidRequestError):
    """Raised when a filter value cannot be parsed to the column's target type."""
    pass


class InvalidDateRangeError(InvalidRequestError):
    """Raised when start_date is after end_date."""
    pass
