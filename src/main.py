import logging
from pathlib import Path
import sys

# Ensure project root is on sys.path when executed directly as a script
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config import config
from src.data.loader import DataLoader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("src.main")


def main() -> None:
    """CLI application entry point."""
    logger.info("NatWest Technical Assessment - Project 4: Agentic Data Analysis")
    logger.info("Initializing dataset from: %s", config.data_path)
    
    loader = DataLoader()
    context = loader.load()
    
    logger.info(
        "Ready. Loaded %d transactions and %d evaluation questions.",
        len(context.transactions),
        len(context.evaluation_questions),
    )


if __name__ == "__main__":
    main()

