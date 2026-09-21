"""Custom exceptions for tool registry and tool execution layers."""


class ToolError(Exception):
    """Base exception for all tool layer errors."""
    pass


class ToolNotFoundError(ToolError, KeyError):
    """Raised when an unregistered tool is requested for execution."""
    pass


class InvalidToolArgumentError(ToolError, ValueError):
    """Raised when arguments passed to a tool cannot be parsed or coerced."""
    pass
