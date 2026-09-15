from typing import Protocol


class ILLMClient(Protocol):
    def complete(self, prompt: str, context: list[str]) -> str: ...


class IRetriever(Protocol):
    def retrieve(self, query: str) -> list[str]: ...
