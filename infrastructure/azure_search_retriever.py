from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.identity import DefaultAzureCredential
from domain.interfaces import IRetriever, IEmbeddingClient


class AzureSearchRetriever(IRetriever):
    def __init__(self, endpoint: str, index_name: str, embedding_client: IEmbeddingClient):
        self._client = SearchClient(
            endpoint, index_name, DefaultAzureCredential())
        self._embedding_client = embedding_client

    def retrieve(self, query: str) -> list[str]:
        vector = self._embedding_client.embed(query)
        vector_query = VectorizedQuery(
            vector=vector, k_nearest_neighbors=3, fields="text_vector"
        )
        results = self._client.search(
            search_text=query,               # componente keyword
            # componente vettoriale → ricerca ibrida
            vector_queries=[vector_query],
            top=3,
        )
        return [r["chunk"] for r in results]
