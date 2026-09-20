"""Deterministic metric calculation logic."""

from decimal import Decimal
from typing import Optional

from src.models import Transaction


class MetricsCalculator:
    """Calculates derived metrics using exact Decimal arithmetic."""

    @staticmethod
    def calculate_gross_amount(units: Optional[int], unit_price: Optional[Decimal]) -> Optional[Decimal]:
        """gross_amount = units * unit_price"""
        if units is None or unit_price is None:
            return None
        return Decimal(units) * unit_price

    @staticmethod
    def calculate_discount_amount(gross_amount: Optional[Decimal], discount: Optional[Decimal]) -> Optional[Decimal]:
        """discount_amount = gross_amount * discount"""
        if gross_amount is None or discount is None:
            return None
        return gross_amount * discount

    @staticmethod
    def calculate_revenue(gross_amount: Optional[Decimal], discount_amount: Optional[Decimal]) -> Optional[Decimal]:
        """revenue = gross_amount - discount_amount"""
        if gross_amount is None or discount_amount is None:
            return None
        return gross_amount - discount_amount
