"""Simple dictionary-based tool registry."""

from typing import Any, Callable, Dict, Optional


class ToolRegistry:
    """Registry mapping tool names to executable callables."""

    def __init__(self) -> None:
        self._tools: Dict[str, Callable[..., Any]] = {}

    def register(self, name: str, handler: Callable[..., Any]) -> None:
        """Registers a capability by name."""
        self._tools[name] = handler

    def get(self, name: str) -> Optional[Callable[..., Any]]:
        """Retrieves a registered tool by name."""
        return self._tools.get(name)

    def is_registered(self, name: str) -> bool:
        """Checks if a tool name is registered."""
        return name in self._tools
