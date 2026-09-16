import logging

from domain.interfaces import ITelemetryClient


class AppInsightsTelemetryClient(ITelemetryClient):
    """Non chiama un SDK di Application Insights direttamente: si appoggia al
    logging standard di Python. Il runtime di Azure Functions intercetta ogni
    log emesso e lo inoltra ad Application Insights automaticamente, purché
    APPLICATIONINSIGHTS_CONNECTION_STRING sia impostata come app setting.
    custom_dimensions è il meccanismo con cui i log diventano campi
    interrogabili (customDimensions) nella tabella 'traces' di App Insights,
    invece di restare testo libero da fare grep."""

    def __init__(self):
        self._logger = logging.getLogger("chatbot.telemetry")

    def track_event(self, name: str, properties: dict | None = None) -> None:
        self._logger.info(name, extra={"custom_dimensions": properties or {}})

    def track_exception(self, properties: dict | None = None) -> None:
        self._logger.exception(
            "chatbot_exception", extra={"custom_dimensions": properties or {}}
        )
