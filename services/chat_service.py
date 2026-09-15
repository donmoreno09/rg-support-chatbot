from domain.interfaces import ILLMClient, IRetriever


class ChatService:
    def __init__(self, retriever: IRetriever, llm: ILLMClient):
        self._retriever = retriever
        self._llm = llm

    def handle(self, message: str) -> str:
        context = self._retriever.retrieve(message)
        return self._llm.complete(message, context)
