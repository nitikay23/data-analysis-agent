"""Unit tests for the PresentationFormatter."""

from decimal import Decimal
import pytest

from src.models import AnalysisResult
from src.presentation.formatter import PresentationFormatter


class TestPresentationFormatter:
    """Tests deterministic formatting of numbers, metrics, and AnalysisResults."""

    def test_format_monetary_decimal(self) -> None:
        """Formats continuous / monetary decimal values with 2 decimal places."""
        formatted = PresentationFormatter.format_number(Decimal("1234.567"), metric_name="revenue")
        assert formatted == "1234.57"

        formatted_exact = PresentationFormatter.format_number(Decimal("100"), metric_name="revenue")
        assert formatted_exact == "100.00"

    def test_format_integer_count(self) -> None:
        """Formats integer and count metrics without decimal points."""
        formatted = PresentationFormatter.format_number(42, metric_name="transaction_count")
        assert formatted == "42"

        formatted_units = PresentationFormatter.format_number(Decimal("150"), metric_name="units")
        assert formatted_units == "150"

    def test_format_discount_percentage(self) -> None:
        """Formats discount rate as percentage."""
        formatted_20 = PresentationFormatter.format_number(Decimal("0.20"), metric_name="discount")
        assert formatted_20 == "20%"

        formatted_12_5 = PresentationFormatter.format_number(Decimal("0.125"), metric_name="discount")
        assert formatted_12_5 == "12.50%"

    def test_format_result_scalar_success(self) -> None:
        """Formats standard scalar AnalysisResult."""
        result = AnalysisResult(
            status="SUCCESS",
            metric="revenue",
            aggregation="sum",
            value=Decimal("5678.90"),
        )
        formatted = PresentationFormatter.format_result(result)
        assert formatted == "5678.90"

    def test_format_result_grouped_values(self) -> None:
        """Formats grouped AnalysisResult with alphabetically sorted keys."""
        result = AnalysisResult(
            status="SUCCESS",
            metric="revenue",
            aggregation="sum",
            group_by="region",
            grouped_values={
                "US": Decimal("3000.50"),
                "APAC": Decimal("1500.25"),
                "EMEA": Decimal("2000.00"),
            },
        )
        formatted = PresentationFormatter.format_result(result)
        assert formatted == "APAC: 1500.25, EMEA: 2000.00, US: 3000.50"

    def test_format_result_partial_status(self) -> None:
        """Includes note about excluded missing records when status is PARTIAL."""
        result = AnalysisResult(
            status="PARTIAL",
            metric="revenue",
            aggregation="mean",
            value=Decimal("120.50"),
            excluded_missing_count=3,
        )
        formatted = PresentationFormatter.format_result(result)
        assert formatted == "120.50 (Note: 3 records were excluded due to missing values)"

    def test_format_result_no_data(self) -> None:
        """Formats NO_DATA status clearly."""
        result = AnalysisResult(
            status="NO_DATA",
            metric="revenue",
            aggregation="sum",
            explanation="No records matched filter criteria.",
        )
        formatted = PresentationFormatter.format_result(result)
        assert "No matching records found" in formatted

    def test_format_result_unknown_dimension(self) -> None:
        """Formats UNKNOWN_DIMENSION_VALUE status clearly."""
        result = AnalysisResult(
            status="UNKNOWN_DIMENSION_VALUE",
            metric="revenue",
            aggregation="sum",
            error_message="Unknown dimension value 'Mars' for column 'region'",
        )
        formatted = PresentationFormatter.format_result(result)
        assert "Unknown dimension value" in formatted
        assert "Mars" in formatted

    def test_format_result_invalid_request(self) -> None:
        """Formats INVALID_REQUEST status clearly."""
        result = AnalysisResult(
            status="INVALID_REQUEST",
            error_message="Unsupported metric 'profit'",
        )
        formatted = PresentationFormatter.format_result(result)
        assert "Invalid request" in formatted
        assert "Unsupported metric" in formatted
