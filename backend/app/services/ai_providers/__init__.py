"""
ai_providers/__init__.py — AI Provider Adapters Package
Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework

All provider adapters implement the AIProviderBase abstract class:
- OpenAIProvider
- AzureOpenAIProvider
- AnthropicProvider
- GeminiProvider
- OllamaProvider
- CustomRESTProvider
"""
from app.services.ai_providers.openai_provider import OpenAIProvider
from app.services.ai_providers.azure_provider import AzureOpenAIProvider
from app.services.ai_providers.anthropic_provider import AnthropicProvider
from app.services.ai_providers.gemini_provider import GeminiProvider
from app.services.ai_providers.ollama_provider import OllamaProvider
from app.services.ai_providers.custom_provider import CustomRESTProvider

__all__ = [
    "OpenAIProvider",
    "AzureOpenAIProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "OllamaProvider",
    "CustomRESTProvider",
]

