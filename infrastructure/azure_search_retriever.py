import logging

from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.identity import DefaultAzureCredential
from domain.interfaces import IRetriever, IEmbeddingClient


class AzureSearchRetriever(IRetriever):
    def __init__(
        self,
        endpoint: str,
        index_name: str,
        embedding_client: IEmbeddingClient,
        score_threshold: float = 0.60,
    ):
        self._client = SearchClient(
            endpoint, index_name, DefaultAzureCredential())
        self._embedding_client = embedding_client
        self._score_threshold = score_threshold

    def retrieve(self, query: str) -> list[str]:
        vector = self._embedding_client.embed(query)
        vector_query = VectorizedQuery(
            vector=vector, k_nearest_neighbors=3, fields="text_vector"
        )
        results = list(self._client.search(
            # niente keyword: score = similarità coseno pura, interpretabile
            search_text=None,
            vector_queries=[vector_query],
            top=3,
        ))

        for r in results:
            logging.info(f"score={r['@search.score']:.4f} chunk={r['chunk'][:40]!r}")

        return [
            r["chunk"] for r in results
            if r["@search.score"] >= self._score_threshold
        ]
