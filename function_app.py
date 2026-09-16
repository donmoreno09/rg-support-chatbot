import azure.functions as func
import json
import uuid
import logging

from services.chat_service import ChatService
from domain.interfaces import ILLMClient, IRetriever
from infrastructure.azure_openai_client import AzureOpenAIClient
from infrastructure.azure_search_retriever import AzureSearchRetriever
from infrastructure.azure_openai_embedding_client import AzureOpenAIEmbeddingClient
from infrastructure.app_insights_telemetry_client import AppInsightsTelemetryClient
from infrastructure.azure_queue_publisher import AzureQueuePublisher

COMPLEXITY_THRESHOLD = 200  # caratteri — soglia arbitraria, solo per simulare il caso

app = func.FunctionApp()


class EchoLLMClient(ILLMClient):
    """Finto LLM: ripete il messaggio. Lo sostituiamo con Azure OpenAI in Fase 2."""

    def complete(self, prompt: str, context: list[str]) -> str:
        return f"hai detto: {prompt}"


class EmptyRetriever(IRetriever):
    """Nessun contesto per ora. Lo sostituiamo con Azure AI Search in Fase 3."""

    def retrieve(self, query: str) -> list[str]:
        return []


embedding_client = AzureOpenAIEmbeddingClient(
    endpoint="https://oai-support-chatbot.openai.azure.com/",
    deployment="embed-deploy",
)

retriever = AzureSearchRetriever(
    endpoint="https://search-supportchatbot-don.search.windows.net",
    index_name="faq",
    embedding_client=embedding_client,
)

telemetry = AppInsightsTelemetryClient()

chat_service = ChatService(retriever=retriever, llm_client=AzureOpenAIClient(
    endpoint="https://oai-support-chatbot.openai.azure.com/", deployment="chat-deploy"), telemetry=telemetry,)


@app.route(route="chat", auth_level=func.AuthLevel.ANONYMOUS)
@app.queue_output(arg_name="queueMsg", queue_name="complex-queries", connection="AzureWebJobsStorage")
def chat(req: func.HttpRequest, queueMsg: func.Out[str]) -> func.HttpResponse:
    body = req.get_json()
    message = body.get("message", "")

    if len(message) > COMPLEXITY_THRESHOLD:
        request_id = str(uuid.uuid4())
        publisher = AzureQueuePublisher(queueMsg)
        publisher.publish({"request_id": request_id, "message": message})
        return func.HttpResponse(
            json.dumps({"status": "accepted", "request_id": request_id}),
            status_code=202,
            mimetype="application/json"
        )

    reply = chat_service.handle(message)
    return func.HttpResponse(
        json.dumps({"reply": reply}),
        mimetype="application/json",
        status_code=200
    )


@app.queue_trigger(arg_name="msg", queue_name="complex-queries",
                   connection="AzureWebJobsStorage")
def process_complex_query(msg: func.QueueMessage) -> None:
    payload = json.loads(msg.get_body().decode("utf-8"))
    request_id = payload["request_id"]
    message = payload["message"]

    # identica logica dell'endpoint sincrono
    reply = chat_service.handle(message)

    logging.info(
        "complex_query_completed",
        extra={"custom_dimensions": {
            "request_id": request_id, "reply_length": len(reply)}},
    )
    # Qui in un sistema reale salveresti il risultato da qualche parte
    # (es. Cosmos DB, un'altra coda di risposta) associato a request_id.
