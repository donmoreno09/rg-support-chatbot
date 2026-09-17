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

class ITicketService(ABC):
    """Astrazione per l'apertura di un ticket quando il bot non trova contesto
    sufficiente per rispondere con sicurezza. Chi la usa non sa se dietro c'è
    un vero sistema di ticketing enterprise o, come in questo progetto
    dimostrativo, un webhook fittizio — se domani cambia il sistema reale,
    non si tocca ChatService."""

    @abstractmethod
    def create_ticket(self, message: str, reason: str) -> str: ...
