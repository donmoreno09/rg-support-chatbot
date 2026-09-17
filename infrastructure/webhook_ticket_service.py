import uuid
import requests

from domain.interfaces import ITicketService


class WebhookTicketService(ITicketService):
    """Implementazione dimostrativa: invia il ticket a un webhook fittizio
    invece che a un vero sistema enterprise. In un progetto reale, solo
    questa classe cambierebbe (es. una SalesforceTicketService) — il resto
    del sistema continuerebbe a dipendere solo da ITicketService."""

    def __init__(self, webhook_url: str):
        self._webhook_url = webhook_url

    def create_ticket(self, message: str, reason: str) -> str:
        ticket_id = str(uuid.uuid4())
        requests.post(
            self._webhook_url,
            json={"ticket_id": ticket_id, "message": message, "reason": reason},
            timeout=5,
        )
        return ticket_id
