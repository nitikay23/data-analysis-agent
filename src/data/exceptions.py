"""Custom exceptions for dataset loading and validation."""


class DataError(Exception):
    """Base exception for all data layer errors."""
    pass


class DatasetNotFoundError(DataError, FileNotFoundError):
    """Raised when the configured dataset file cannot be found."""
    pass


class DataValidationError(DataError, ValueError):
    """Raised when dataset structure, schema, or record values fail validation."""
    pass
