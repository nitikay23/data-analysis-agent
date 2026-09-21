"""Custom exceptions for LLM client providers and prompt generation."""


class LLMError(Exception):
    """Base exception for all LLM client errors."""
    pass


class LLMConnectionError(LLMError):
    """Raised when the LLM provider endpoint cannot be reached or times out."""
    pass


class LLMResponseParsingError(LLMError):
    """Raised when the LLM response cannot be parsed into a valid JSON tool call."""
    pass
