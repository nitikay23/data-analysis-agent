"""Tests for the CLI application entry point."""

from pathlib import Path
import pytest

from src.main import build_agent, main, parse_args


class TestCLIEntryPoint:
    """Tests command-line argument parsing and end-to-end main() execution."""

    def test_parse_args_positional_query(self) -> None:
        args = parse_args(["What is total revenue?", "--mock"])
        assert args.query == "What is total revenue?"
        assert args.mock is True

    def test_parse_args_flag_query(self) -> None:
        args = parse_args(["-q", "How many Beta transactions?", "--mock"])
        assert args.flag_query == "How many Beta transactions?"
        assert args.mock is True

    def test_build_agent_with_mock(self) -> None:
        orchestrator, loader = build_agent(use_mock=True)
        assert orchestrator is not None
        assert loader is not None

    def test_main_with_mock_query(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Runs single query via main CLI."""
        exit_code = main(["What is the total revenue for UK transactions?", "--mock"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "4320.00" in captured.out

    def test_main_with_eval_mode(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Runs full evaluation benchmark through main CLI."""
        exit_code = main(["--eval", "--mock"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Q001" in captured.out
        assert "4320.00" in captured.out
        assert "Q003" in captured.out
        assert "The region with the highest total revenue is DE, with 5350.00." in captured.out
        assert "Q009" in captured.out
        assert "Guardrail rejection" in captured.out
        assert "Q010" in captured.out
        assert "Unknown dimension value" in captured.out
