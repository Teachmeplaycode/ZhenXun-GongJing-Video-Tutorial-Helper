"""Chat model access (OpenAI-compatible such as DeepSeek, or a local Ollama)."""
from .client import (ChatClient, LLMConfig, LLMError, OllamaClient, ToolCall, Usage, assistant_message, create_client,
                     tool_message)

__all__ = ["ChatClient", "LLMConfig", "LLMError", "OllamaClient", "ToolCall", "Usage", "assistant_message",
           "create_client", "tool_message"]
