"""LLM Client interface isolating provider implementation."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class LLMClient(ABC):
    """Abstract interface for LLM client providers."""

    @abstractmethod
    def generate_tool_call(self, prompt: str) -> Dict[str, Any]:
        """Generates a structured tool call request from natural-language prompt."""
        raise NotImplementedError
