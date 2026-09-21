"""CSV loader and validator separating transactions from evaluation questions."""

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.config import config
from src.data.exceptions import DatasetNotFoundError, DataValidationError
from src.data.schema import EvaluationQuestionSchema, RawCSVSchema, TransactionSchema
from src.models import DatasetContext, EvaluationQuestion, Transaction

logger = logging.getLogger(__name__)


class DataLoader:
    """Loads, validates, and normalizes raw CSV records into trusted internal views."""

    def __init__(self, file_path: Optional[Path] = None) -> None:
        # Step 1: Resolve CSV path from centralized configuration
        self.file_path: Path = file_path or config.get_resolved_data_path()

    def load(self) -> DatasetContext:
        """Executes full loading, structural validation, record splitting, and type normalization."""
        logger.info("Dataset load started: %s", self.file_path)

        if not self.file_path.is_file():
            raise DatasetNotFoundError(f"Dataset file not found at path: {self.file_path}")

        # Step 2: Load raw CSV
        raw_rows, header_fields = self._read_raw_csv()
        logger.info("Raw dataset loaded from %s (%d rows)", self.file_path, len(raw_rows))

        # Step 3: Validate raw structural schema
        self._validate_raw_schema(header_fields)

        # Step 4, 5, 6, 7: Classify rows, validate IDs, and construct raw views
        raw_tx_views, raw_q_views = self._classify_and_split_records(raw_rows)
        logger.info(
            "Identified %d transaction records and %d evaluation questions",
            len(raw_tx_views),
            len(raw_q_views),
        )

        # Step 8 & 10: Validate transaction data and normalize trusted types
        transactions = self._validate_and_normalize_transactions(raw_tx_views)

        # Step 9: Validate evaluation question data
        evaluation_questions = self._validate_evaluation_questions(raw_q_views)

        logger.info(
            "Dataset validation completed successfully: %d transactions, %d evaluation questions",
            len(transactions),
            len(evaluation_questions),
        )

        # Step 11: Return trusted DatasetContext
        return DatasetContext(
            transactions=transactions,
            evaluation_questions=evaluation_questions,
        )

    def _read_raw_csv(self) -> Tuple[List[Tuple[int, Dict[str, str]]], List[str]]:
        """Reads raw CSV rows without modifying the source file."""
        raw_rows: List[Tuple[int, Dict[str, str]]] = []
        try:
            with open(self.file_path, mode="r", encoding="utf-8-sig") as csv_file:
                reader = csv.DictReader(csv_file)
                if reader.fieldnames is None:
                    raise DataValidationError(
                        f"Dataset file '{self.file_path}' is empty or missing headers."
                    )
                header_fields = [f.strip() for f in reader.fieldnames if f]

                for line_num, raw_row in enumerate(reader, start=2):
                    cleaned_row = {
                        k.strip(): (v.strip() if v is not None else "")
                        for k, v in raw_row.items()
                        if k
                    }
                    raw_rows.append((line_num, cleaned_row))

            return raw_rows, header_fields
        except (UnicodeDecodeError, csv.Error) as e:
            raise DataValidationError(f"Malformed CSV content in file '{self.file_path}': {e}") from e

    def _validate_raw_schema(self, header_fields: List[str]) -> None:
        """Step 3: Validate that all required columns are present in the raw CSV header."""
        actual_columns = set(header_fields)
        missing_columns = RawCSVSchema.REQUIRED_COLUMNS - actual_columns
        if missing_columns:
            raise DataValidationError(
                f"Dataset is missing required column(s): {sorted(missing_columns)}"
            )

    def _classify_and_split_records(
        self, raw_rows: List[Tuple[int, Dict[str, str]]]
    ) -> Tuple[List[Tuple[int, Dict[str, str]]], List[Tuple[int, Dict[str, str]]]]:
        """Steps 4, 5, 6, 7: Validate IDs, classify records by prefix, and create isolated raw views."""
        raw_tx_views: List[Tuple[int, Dict[str, str]]] = []
        raw_q_views: List[Tuple[int, Dict[str, str]]] = []

        for line_num, row in raw_rows:
            record_id = row.get("id", "")
            if not record_id:
                raise DataValidationError(f"Row {line_num}: Missing required 'id' field.")

            if record_id.startswith(RawCSVSchema.TRANSACTION_ID_PREFIX):
                # Construct logical transaction view (strictly copy transaction columns only, omit 'question')
                tx_view = {
                    col: row.get(col, "")
                    for col in TransactionSchema.COLUMNS
                }
                raw_tx_views.append((line_num, tx_view))

            elif record_id.startswith(RawCSVSchema.EVALUATION_ID_PREFIX):
                # Construct logical evaluation question view
                q_view = {
                    col: row.get(col, "")
                    for col in EvaluationQuestionSchema.COLUMNS
                }
                raw_q_views.append((line_num, q_view))

            else:
                raise DataValidationError(
                    f"Row {line_num}: Unrecognized record ID prefix '{record_id}'. "
                    f"Expected '{RawCSVSchema.TRANSACTION_ID_PREFIX}' for transactions "
                    f"or '{RawCSVSchema.EVALUATION_ID_PREFIX}' for evaluation questions."
                )

        return raw_tx_views, raw_q_views

    def _validate_and_normalize_transactions(
        self, raw_tx_views: List[Tuple[int, Dict[str, str]]]
    ) -> List[Transaction]:
        """Steps 8 & 10: Validate required fields and normalize types into trusted Transaction models."""
        transactions: List[Transaction] = []

        for line_num, row in raw_tx_views:
            record_id = row["id"]

            # Validate date
            raw_date = row.get("date", "")
            if not raw_date:
                raise DataValidationError(
                    f"Row {line_num} (ID {record_id}): Missing required 'date' field."
                )
            try:
                parsed_date = date.fromisoformat(raw_date)
            except ValueError as e:
                raise DataValidationError(
                    f"Row {line_num} (ID {record_id}): Invalid date format '{raw_date}'. Expected YYYY-MM-DD."
                ) from e

            # Validate categorical string fields
            region = row.get("region", "")
            if not region:
                raise DataValidationError(
                    f"Row {line_num} (ID {record_id}): Missing required 'region' field."
                )

            product = row.get("product", "")
            if not product:
                raise DataValidationError(
                    f"Row {line_num} (ID {record_id}): Missing required 'product' field."
                )

            # Normalize numeric fields (int / Decimal)
            raw_units = row.get("units", "")
            units: Optional[int] = None
            if raw_units:
                try:
                    units = int(raw_units)
                except ValueError as e:
                    raise DataValidationError(
                        f"Row {line_num} (ID {record_id}): Invalid integer value for 'units': '{raw_units}'."
                    ) from e

            raw_unit_price = row.get("unit_price", "")
            unit_price: Optional[Decimal] = None
            if raw_unit_price:
                try:
                    unit_price = Decimal(raw_unit_price)
                except InvalidOperation as e:
                    raise DataValidationError(
                        f"Row {line_num} (ID {record_id}): Invalid Decimal value for 'unit_price': '{raw_unit_price}'."
                    ) from e

            raw_discount = row.get("discount", "")
            discount: Optional[Decimal] = None
            if raw_discount:
                try:
                    discount = Decimal(raw_discount)
                except InvalidOperation as e:
                    raise DataValidationError(
                        f"Row {line_num} (ID {record_id}): Invalid Decimal value for 'discount': '{raw_discount}'."
                    ) from e

            transactions.append(
                Transaction(
                    id=record_id,
                    date=parsed_date,
                    region=region,
                    product=product,
                    units=units,
                    unit_price=unit_price,
                    discount=discount,
                )
            )

        return transactions

    def _validate_evaluation_questions(
        self, raw_q_views: List[Tuple[int, Dict[str, str]]]
    ) -> List[EvaluationQuestion]:
        """Step 9: Validate evaluation question records."""
        questions: List[EvaluationQuestion] = []

        for line_num, row in raw_q_views:
            record_id = row["id"]
            question_text = row.get("question", "")
            if not question_text:
                raise DataValidationError(
                    f"Row {line_num} (ID {record_id}): Missing required 'question' text."
                )

            questions.append(
                EvaluationQuestion(
                    id=record_id,
                    question=question_text,
                )
            )

        return questions
