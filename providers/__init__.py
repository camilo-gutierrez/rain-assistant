from .base import BaseProvider, NormalizedEvent


def get_provider(provider_name: str) -> BaseProvider:
    """Factory: create a provider instance by name."""
    if provider_name == "claude":
        from .claude_provider import ClaudeProvider
        return ClaudeProvider()
    elif provider_name == "openai":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider()
    elif provider_name == "gemini":
        from .gemini_provider import GeminiProvider
        return GeminiProvider()
    elif provider_name == "ollama":
        from .ollama_provider import OllamaProvider
        return OllamaProvider()
    else:
        raise ValueError(f"Unknown provider: {provider_name}")


__all__ = ["get_provider", "BaseProvider", "NormalizedEvent"]
