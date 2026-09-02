from abc import ABC, abstractmethod
from functools import lru_cache

from app.core.config import settings


class LLMProvider(ABC):
    """Swap mock → Ollama → Azure OpenAI without touching call sites."""

    @abstractmethod
    def complete(self, prompt: str, *, system: str | None = None) -> str: ...

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class MockLLMProvider(LLMProvider):
    def complete(self, prompt: str, *, system: str | None = None) -> str:
        prefix = (system or "assistant").split()[0]
        return f"[mock:{prefix}] {prompt[:240]}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        # Deterministic tiny vectors for local RAG plumbing tests
        return [[float((sum(ord(c) for c in t) % 97) + i) for i in range(8)] for t in texts]


@lru_cache
def get_llm_provider() -> LLMProvider:
    if settings.llm_provider == "mock":
        return MockLLMProvider()
    # Future: ollama / azure_openai adapters
    return MockLLMProvider()
