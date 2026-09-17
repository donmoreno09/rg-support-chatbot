import time

from domain.interfaces import ILLMClient, IRetriever, ITelemetryClient, ITicketService


class ChatService:
    def __init__(
        self,
        llm_client: ILLMClient,
        retriever: IRetriever,
        telemetry: ITelemetryClient,
        ticket_service: ITicketService,
    ):
        self._llm_client = llm_client
        self._retriever = retriever
        self._telemetry = telemetry
        self._ticket_service = ticket_service

    def handle(self, message: str) -> str:
        context = self._retriever.retrieve(message)

        if not context:
            self._telemetry.track_event("retrieval_empty", {"query": message})
            ticket_id = self._ticket_service.create_ticket(
                message=message,
                reason="Nessun contesto trovato nella knowledge base",
            )
            self._telemetry.track_event(
                "escalated_to_ticket", {
                    "query": message, "ticket_id": ticket_id}
            )
            return (
                f"Non ho trovato informazioni sufficienti per risponderti con "
                f"certezza. Ho aperto il ticket {ticket_id}: un operatore ti "
                f"contatterà a breve."
            )

        start = time.monotonic()
        try:
            reply = self._llm_client.complete(message, context)
        except Exception:
            self._telemetry.track_exception({"query": message})
            raise
        duration_ms = (time.monotonic() - start) * 1000

        self._telemetry.track_event(
            "llm_call_completed",
            {"duration_ms": duration_ms, "context_chunks": len(context)},
        )
        return reply
