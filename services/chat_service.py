import time

from domain.interfaces import ILLMClient, IRetriever, ITelemetryClient


class ChatService:
    def __init__(
        self,
        llm_client: ILLMClient,
        retriever: IRetriever,
        telemetry: ITelemetryClient,
    ):
        self._llm_client = llm_client
        self._retriever = retriever
        self._telemetry = telemetry

    def handle(self, message: str) -> str:
        context = self._retriever.retrieve(message)

        if not context:
            self._telemetry.track_event("retrieval_empty", {"query": message})

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
