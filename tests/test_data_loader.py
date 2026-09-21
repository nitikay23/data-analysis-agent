"""Tests for raw CSV splitting, schema boundary enforcement, and trusted data views."""

from dataclasses import fields
from datetime import date
from decimal import Decimal
import hashlib
from pathlib import Path
import pytest

from src.config import config
from src.data.exceptions import DatasetNotFoundError, DataValidationError
from src.data.loader import DataLoader
from src.data.schema import (
    EvaluationQuestionSchema,
    RawCSVSchema,
    TransactionSchema,
)

from src.models import DatasetContext, EvaluationQuestion, Transaction



@pytest.fixture
def sample_csv_content() -> str:
    return """id,date,region,product,units,unit_price,discount,question
T001,2026-01-03,UK,Alpha,10,100,0.10,
T002,2026-01-05,DE,Beta,5,200.50,0.00,
Q001,,,,,,,"What is the total revenue for UK transactions?"
Q002,,,,,,,"What is the average number of units per transaction?"
"""


@pytest.fixture
def sample_csv_file(tmp_path: Path, sample_csv_content: str) -> Path:
    csv_file = tmp_path / "sample_data.csv"
    csv_file.write_text(sample_csv_content, encoding="utf-8")
    return csv_file


def test_supplied_csv_loads_successfully(sample_csv_file: Path):
    """Requirement 1: The CSV loads successfully into a trusted DatasetContext."""
    loader = DataLoader(file_path=sample_csv_file)
    context = loader.load()

    assert isinstance(context, DatasetContext)
    assert len(context.transactions) == 2
    assert len(context.evaluation_questions) == 2


def test_all_t_rows_become_transactions(sample_csv_file: Path):
    """Requirement 2: All T-prefixed rows become transactions."""
    loader = DataLoader(file_path=sample_csv_file)
    context = loader.load()

    assert all(isinstance(tx, Transaction) for tx in context.transactions)
    assert all(tx.id.startswith("T") for tx in context.transactions)
    assert [tx.id for tx in context.transactions] == ["T001", "T002"]


def test_all_q_rows_become_evaluation_questions(sample_csv_file: Path):
    """Requirement 3: All Q-prefixed rows become evaluation questions."""
    loader = DataLoader(file_path=sample_csv_file)
    context = loader.load()

    assert all(isinstance(q, EvaluationQuestion) for q in context.evaluation_questions)
    assert all(q.id.startswith("Q") for q in context.evaluation_questions)
    assert [q.id for q in context.evaluation_questions] == ["Q001", "Q002"]


def test_transaction_view_does_not_contain_question(sample_csv_file: Path):
    """Requirement 4: Transaction model / view does NOT contain 'question'."""
    loader = DataLoader(file_path=sample_csv_file)
    context = loader.load()

    tx = context.transactions[0]
    assert not hasattr(tx, "question")
    tx_field_names = {f.name for f in fields(Transaction)}
    assert "question" not in tx_field_names
    assert tx_field_names == TransactionSchema.COLUMNS


def test_evaluation_question_view_contains_id_and_question(sample_csv_file: Path):
    """Requirement 5: Evaluation-question view contains id and question."""
    loader = DataLoader(file_path=sample_csv_file)
    context = loader.load()

    q = context.evaluation_questions[0]
    assert hasattr(q, "id")
    assert hasattr(q, "question")
    assert q.id == "Q001"
    assert q.question == "What is the total revenue for UK transactions?"
    q_field_names = {f.name for f in fields(EvaluationQuestion)}
    assert q_field_names == EvaluationQuestionSchema.COLUMNS


def test_original_csv_is_not_modified(sample_csv_file: Path):
    """Requirement 6: Original CSV source file remains completely unchanged after loading."""
    initial_content = sample_csv_file.read_bytes()
    initial_hash = hashlib.sha256(initial_content).hexdigest()

    loader = DataLoader(file_path=sample_csv_file)
    _ = loader.load()

    post_load_content = sample_csv_file.read_bytes()
    post_load_hash = hashlib.sha256(post_load_content).hexdigest()

    assert initial_hash == post_load_hash
    assert initial_content == post_load_content


def test_unsupported_id_prefix_rejected(tmp_path: Path):
    """Requirement 7: Records with unsupported ID prefixes raise DataValidationError."""
    csv_file = tmp_path / "invalid_prefix.csv"
    csv_file.write_text(
        "id,date,region,product,units,unit_price,discount,question\n"
        "X001,2026-01-03,UK,Alpha,10,100,0.10,\n",
        encoding="utf-8",
    )

    with pytest.raises(DataValidationError) as exc_info:
        DataLoader(file_path=csv_file).load()

    assert "unrecognized record id prefix" in str(exc_info.value).lower()
    assert "X001" in str(exc_info.value)


def test_missing_id_rejected(tmp_path: Path):
    """Requirement 8: Missing ID raises DataValidationError."""
    csv_file = tmp_path / "missing_id.csv"
    csv_file.write_text(
        "id,date,region,product,units,unit_price,discount,question\n"
        ",2026-01-03,UK,Alpha,10,100,0.10,\n",
        encoding="utf-8",
    )

    with pytest.raises(DataValidationError) as exc_info:
        DataLoader(file_path=csv_file).load()

    assert "missing required 'id' field" in str(exc_info.value).lower()


def test_missing_required_transaction_columns_rejected(tmp_path: Path):
    """Requirement 9: Missing required raw schema columns in CSV header raises DataValidationError."""
    csv_file = tmp_path / "missing_columns.csv"
    # Omit 'units' and 'question'
    csv_file.write_text(
        "id,date,region,product,unit_price,discount\n"
        "T001,2026-01-03,UK,Alpha,100,0.10\n",
        encoding="utf-8",
    )

    with pytest.raises(DataValidationError) as exc_info:
        DataLoader(file_path=csv_file).load()

    assert "missing required column" in str(exc_info.value).lower()
    assert "units" in str(exc_info.value)
    assert "question" in str(exc_info.value)


def test_invalid_transaction_date_rejected(tmp_path: Path):
    """Requirement 10: Invalid date in transaction record raises DataValidationError."""
    csv_file = tmp_path / "bad_date.csv"
    csv_file.write_text(
        "id,date,region,product,units,unit_price,discount,question\n"
        "T001,2026-02-30,UK,Alpha,10,100,0.10,\n",
        encoding="utf-8",
    )

    with pytest.raises(DataValidationError) as exc_info:
        DataLoader(file_path=csv_file).load()

    assert "invalid date format" in str(exc_info.value).lower()


def test_invalid_transaction_numeric_value_rejected(tmp_path: Path):
    """Requirement 11: Malformed numeric values for units, unit_price, or discount raise DataValidationError."""
    # Bad units
    csv_units = tmp_path / "bad_units.csv"
    csv_units.write_text(
        "id,date,region,product,units,unit_price,discount,question\n"
        "T001,2026-01-03,UK,Alpha,TEN,100,0.10,\n",
        encoding="utf-8",
    )
    with pytest.raises(DataValidationError) as exc_units:
        DataLoader(file_path=csv_units).load()
    assert "units" in str(exc_units.value).lower()

    # Bad unit_price
    csv_price = tmp_path / "bad_price.csv"
    csv_price.write_text(
        "id,date,region,product,units,unit_price,discount,question\n"
        "T001,2026-01-03,UK,Alpha,10,invalid_price,0.10,\n",
        encoding="utf-8",
    )
    with pytest.raises(DataValidationError) as exc_price:
        DataLoader(file_path=csv_price).load()
    assert "unit_price" in str(exc_price.value).lower()

    # Bad discount
    csv_disc = tmp_path / "bad_disc.csv"
    csv_disc.write_text(
        "id,date,region,product,units,unit_price,discount,question\n"
        "T001,2026-01-03,UK,Alpha,10,100,invalid_discount,\n",
        encoding="utf-8",
    )
    with pytest.raises(DataValidationError) as exc_disc:
        DataLoader(file_path=csv_disc).load()
    assert "discount" in str(exc_disc.value).lower()


def test_empty_evaluation_question_rejected(tmp_path: Path):
    """Requirement 12: Empty question in evaluation record raises DataValidationError."""
    csv_file = tmp_path / "empty_question.csv"
    csv_file.write_text(
        "id,date,region,product,units,unit_price,discount,question\n"
        "Q001,,,,,,,\n",
        encoding="utf-8",
    )

    with pytest.raises(DataValidationError) as exc_info:
        DataLoader(file_path=csv_file).load()

    assert "missing required 'question' text" in str(exc_info.value).lower()


def test_transaction_and_evaluation_counts_for_supplied_dataset():
    """Requirement 13: Supplied dataset loads exactly 10 transactions (T001-T010) and 10 questions (Q001-Q010)."""
    loader = DataLoader()
    context = loader.load()

    assert len(context.transactions) == 10
    assert len(context.evaluation_questions) == 10

    tx_ids = [tx.id for tx in context.transactions]
    expected_tx_ids = [f"T{i:03d}" for i in range(1, 11)]
    assert tx_ids == expected_tx_ids

    q_ids = [q.id for q in context.evaluation_questions]
    expected_q_ids = [f"Q{i:03d}" for i in range(1, 11)]
    assert q_ids == expected_q_ids


def test_nonexistent_file_raises_dataset_not_found(tmp_path: Path):
    """Missing file raises DatasetNotFoundError."""
    loader = DataLoader(file_path=tmp_path / "nonexistent.csv")
    with pytest.raises(DatasetNotFoundError):
        loader.load()
