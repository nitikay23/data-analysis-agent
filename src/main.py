"""Main entry point for CLI."""

from pathlib import Path
import sys

# Ensure project root is on sys.path when executed directly as a script
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config import config


def main() -> None:
    """CLI application entry point."""
    print("NatWest Technical Assessment - Project 4: Agentic Data Analysis")
    print(f"Data source configured: {config.data_path}")


if __name__ == "__main__":
    main()
