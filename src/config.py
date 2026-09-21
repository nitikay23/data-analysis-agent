"""Application and LLM configuration settings."""

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    """Immutable application configuration."""
    
    # Path configuration
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_path: Path = Path(os.getenv("DATA_PATH", "data/project_4.csv"))
    
    # LLM / Ollama configuration placeholders
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    llm_model: str = os.getenv("LLM_MODEL", "llama3.2")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))

    def get_resolved_data_path(self) -> Path:
        """Returns the absolute resolved path to the dataset."""
        if self.data_path.is_absolute():
            return self.data_path
        return (self.base_dir / self.data_path).resolve()


# Default configuration instance
config = AppConfig()

