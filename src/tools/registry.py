"""Dictionary-based tool registry for managing and dispatching registered tools."""

import logging
from typing import Any, Callable, Dict, Optional

from src.tools.exceptions import ToolNotFoundError

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry mapping tool names to executable callables with deterministic dispatching."""

    def __init__(self) -> None:
        self._tools: Dict[str, Callable[..., Any]] = {}

    def register(self, name: str, handler: Callable[..., Any]) -> None:
        """Registers an executable tool handler by name."""
        if not name or not isinstance(name, str):
            raise ValueError("Tool name must be a non-empty string.")
        if not callable(handler):
            raise TypeError(f"Handler for tool '{name}' must be callable.")

        self._tools[name] = handler
        logger.info("Registered tool: '%s'", name)

    def get(self, name: str) -> Optional[Callable[..., Any]]:
        """Retrieves a registered tool handler by name or returns None."""
        return self._tools.get(name)

    def is_registered(self, name: str) -> bool:
        """Checks whether a tool is registered."""
        return name in self._tools

    def execute(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Dispatches execution to the registered tool handler with unpacked arguments.

        Raises:
            ToolNotFoundError: If the tool is not registered.
        """
        handler = self.get(name)
        if handler is None:
            logger.warning("Execution failed: Tool '%s' is not registered.", name)
            raise ToolNotFoundError(f"Tool '{name}' is not registered.")

        args = arguments if arguments is not None else {}
        logger.info("Executing registered tool '%s'", name)
        return handler(**args)
