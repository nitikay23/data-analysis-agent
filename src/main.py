"""CLI application entry point for the Agentic Data Analysis system."""

import argparse
import logging
from pathlib import Path
import sys
from typing import Optional

# Ensure project root is on sys.path when executed directly as a script
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.agent.orchestrator import AgentOrchestrator
from src.analysis.engine import AnalysisEngine
from src.config import config
from src.data.loader import DataLoader
from src.guardrails.validator import GuardrailValidator
from src.llm.client import MockLLMClient, OllamaLLMClient
from src.presentation.formatter import PresentationFormatter
from src.tools.analysis_tool import AnalysisTool
from src.tools.registry import ToolRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("src.main")


def build_agent(
    data_path: Optional[Path] = None,
    use_mock: bool = False,
) -> tuple[AgentOrchestrator, DataLoader]:
    """Factory initializing and wiring the complete 5-layer pipeline."""
    loader = DataLoader(file_path=data_path)
    context = loader.load()

    engine = AnalysisEngine(context.transactions)
    analysis_tool = AnalysisTool(engine)

    tool_registry = ToolRegistry()
    tool_registry.register("run_analysis", analysis_tool.run)

    guardrail_validator = GuardrailValidator(allowed_tools={"run_analysis"})

    llm_client = (
        MockLLMClient()
        if use_mock or config.use_mock_llm
        else OllamaLLMClient(
            base_url=config.ollama_base_url,
            model=config.llm_model,
            temperature=config.llm_temperature,
        )
    )

    formatter = PresentationFormatter()

    orchestrator = AgentOrchestrator(
        llm_client=llm_client,
        guardrail_validator=guardrail_validator,
        tool_registry=tool_registry,
        formatter=formatter,
    )
    return orchestrator, loader


def parse_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(
        description="NatWest Project 4: Agentic Data Analysis CLI",
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Natural language analysis query (e.g. 'What is the total revenue for UK transactions?')",
    )
    parser.add_argument(
        "-q",
        "--query-flag",
        dest="flag_query",
        default=None,
        help="Alternative flag for natural language query",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=False,
        help="Use deterministic MockLLMClient for testing without live Ollama",
    )
    parser.add_argument(
        "--data-path",
        type=Path,
        default=None,
        help="Custom path to CSV transaction dataset",
    )
    parser.add_argument(
        "--eval",
        action="store_true",
        default=False,
        help="Run all evaluation benchmark questions from dataset",
    )
    return parser.parse_args(args)


def main(args_list: Optional[list[str]] = None) -> int:
    """Main CLI execution flow."""
    args = parse_args(args_list)

    orchestrator, loader = build_agent(
        data_path=args.data_path,
        use_mock=args.mock,
    )

    # 1. Run evaluation benchmark mode if requested
    if args.eval:
        context = loader.load()
        print(f"\nRunning {len(context.evaluation_questions)} benchmark questions:\n" + "=" * 60)
        for q in context.evaluation_questions:
            ans = orchestrator.process_query(q.question)
            print(f"[{q.id}] {q.question}\n-> {ans}\n")
        return 0

    # 2. Run single query mode
    query = args.query or args.flag_query
    if query:
        response = orchestrator.process_query(query)
        print(response)
        return 0

    # 3. Interactive prompt mode fallback
    try:
        user_input = input("Enter analysis query: ").strip()
        if user_input:
            response = orchestrator.process_query(user_input)
            print(response)
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
