from typing import Protocol
from abc import ABC, abstractmethod


class ILLMClient(Protocol):
    def complete(self, prompt: str, context: list[str]) -> str: ...


class IRetriever(Protocol):
    def retrieve(self, query: str) -> list[str]: ...


class IEmbeddingClient(Protocol):
    def embed(self, text: str) -> list[float]: ...


class ITelemetryClient(ABC):
    """Astrazione per l'osservabilità. ChatService dipende da questa interfaccia,
    non da un SDK di monitoring specifico — se domani cambi provider
    (es. da Application Insights a un altro APM), ChatService non cambia."""

    @abstractmethod
    def track_event(self, name: str, properties: dict |
                    None = None) -> None: ...

    @abstractmethod
    def track_exception(self, properties: dict | None = None) -> None: ...


class IQueuePublisher(ABC):
    """Astrazione per instradare un lavoro verso elaborazione asincrona.
    L'endpoint HTTP dipende da questa interfaccia, non da come Azure Storage
    Queue funziona nel dettaglio — se domani cambi meccanismo (es. Service Bus),
    non tocchi function_app.py."""

    @abstractmethod
    def publish(self, message: dict) -> None: ...
