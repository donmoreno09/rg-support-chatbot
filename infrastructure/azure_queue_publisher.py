import json
import azure.functions as func

from domain.interfaces import IQueuePublisher


class AzureQueuePublisher(IQueuePublisher):
    """Wrappa un output binding di Azure Functions dietro l'interfaccia di dominio.
    Il binding viene passato dal function_app al momento della chiamata,
    così questa classe resta testabile senza un vero Storage Account."""

    def __init__(self, queue_binding: func.Out[str]):
        self._queue_binding = queue_binding

    def publish(self, message: dict) -> None:
        self._queue_binding.set(json.dumps(message))