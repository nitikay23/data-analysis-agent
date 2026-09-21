"""Presentation formatter applying domain formatting rules."""

from decimal import Decimal
from typing import Any, Union

from src.models import AnalysisResult


class PresentationFormatter:
    """Formats analysis results according to domain presentation standards."""

    @staticmethod
    def format_number(val: Union[int, float, Decimal], metric_name: str) -> str:
        """Formats numbers: integers without decimals, continuous with 2 decimal places, percentages with %."""
        return str(val)

    @staticmethod
    def format_result(result: AnalysisResult, metric_name: str) -> str:
        """Formats an AnalysisResult for user display."""
        if result.status == "NO_DATA":
            return "NO_DATA"
        return str(result.value)
