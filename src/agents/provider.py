from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], temperature: float = 0.6, max_tokens: int = 800) -> str:
        ...

    @abstractmethod
    def name(self) -> str:
        ...


class MockLLMProvider(LLMProvider):
    def __init__(self, response: str = "") -> None:
        self._response = response

    def chat(self, messages: list[dict], temperature: float = 0.6, max_tokens: int = 800) -> str:
        return self._response

    def name(self) -> str:
        return "mock"
