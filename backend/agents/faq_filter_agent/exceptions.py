"""Custom exceptions for the AI Agent module."""

class AgentError(Exception):
    """Base exception for errors raised by the agent module."""
    pass

class ConfigError(AgentError):
    """Exception raised for errors in configuration."""
    pass

class FAQDataError(AgentError):
    """Exception raised for errors related to FAQ data loading or parsing."""
    pass

class LLMAPIError(AgentError):
    """Exception raised for errors during LLM API calls."""
    pass

class LLMResponseError(LLMAPIError):
    """Exception raised for errors in the LLM API response (e.g., format)."""
    pass 

class PromptLoadError(AgentError):
    """Exception raised when prompt loading fails."""
    pass

class ConfigurationError(AgentError):
    """Exception raised when configuration fails."""
    pass
