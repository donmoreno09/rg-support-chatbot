import azure.functions as func
import json
from services.chat_service import ChatService
from domain.interfaces import ILLMClient, IRetriever

app = func.FunctionApp()


class EchoLLMClient(ILLMClient):
    """Finto LLM: ripete il messaggio. Lo sostituiamo con Azure OpenAI in Fase 2."""

    def complete(self, prompt: str, context: list[str]) -> str:
        return f"hai detto: {prompt}"


class EmptyRetriever(IRetriever):
    """Nessun contesto per ora. Lo sostituiamo con Azure AI Search in Fase 3."""

    def retrieve(self, query: str) -> list[str]:
        return []


chat_service = ChatService(retriever=EmptyRetriever(), llm=EchoLLMClient())


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
