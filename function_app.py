import azure.functions as func
import json
from services.chat_service import ChatService
from domain.interfaces import ILLMClient, IRetriever
from infrastructure.azure_openai_client import AzureOpenAIClient
from infrastructure.azure_search_retriever import AzureSearchRetriever
from infrastructure.azure_openai_embedding_client import AzureOpenAIEmbeddingClient

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

chat_service = ChatService(retriever=retriever, llm=AzureOpenAIClient(
    endpoint="https://oai-support-chatbot.openai.azure.com/", deployment="chat-deploy"))


@app.route(route="chat", auth_level=func.AuthLevel.ANONYMOUS)
def chat(req: func.HttpRequest) -> func.HttpResponse:
    body = req.get_json()
    message = body.get("message", "")
    reply = chat_service.handle(message)
    return func.HttpResponse(
        json.dumps({"reply": reply}),
        mimetype="application/json",
        status_code=200
    )
