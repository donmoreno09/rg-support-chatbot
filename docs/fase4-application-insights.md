# Fase 4 — Application Insights: osservabilità del chatbot

> **Perché questa fase, proprio ora?** Poco fa hai vissuto in prima persona il problema che Application Insights esiste per risolvere: l'endpoint pubblico rispondeva ancora con l'eco di Fase 1, e l'hai scoperto solo a tentativi, lanciando richieste Postman a mano finché non hai notato qualcosa di strano. Con Application Insights collegato, quel disallineamento (codice locale aggiornato, produzione ferma a una versione vecchia) si vede nei log/nelle metriche senza dover indovinare. È anche il requisito esplicitamente citato nell'offerta di lavoro insieme ad Azure Functions e Azure OpenAI — per un ruolo di supporto e troubleshooting di chatbot, è probabilmente lo strumento che userai più spesso.

---

## Prima: chiudiamo la Fase 3 con i commit

Stesso principio di sempre — la history Git riflette i layer che hai aggiunto:

```bash
git add domain/interfaces.py
git commit -m "feat(domain): add IEmbeddingClient interface"

git add infrastructure/azure_openai_embedding_client.py
git commit -m "feat(infrastructure): add AzureOpenAIEmbeddingClient"

git add infrastructure/azure_search_retriever.py
git commit -m "feat(infrastructure): add AzureSearchRetriever with hybrid search"

git add function_app.py
git commit -m "feat(api): wire AzureSearchRetriever into ChatService"

git add infrastructure/
git commit -m "refactor(infrastructure): remove unused EmptyRetriever"
```

Se il redeploy su Azure dopo il fix della Managed Identity non è ancora confermato funzionante sull'endpoint pubblico, non è un problema: il primo step di questa fase te lo farà vedere chiaramente, invece di continuare a indovinare con Postman.

---

## Cosa costruisci in questa Fase 4

- **Verifica** che Application Insights sia già collegato alla Function App (di norma lo è di default se l'hai creata da CLI/portale con monitoring abilitato)
- **Logging strutturato**: usi il modulo `logging` standard di Python — il runtime di Azure Functions lo inoltra automaticamente ad Application Insights, nessun SDK aggiuntivo obbligatorio per i log di base
- **Custom telemetry mirata al dominio**: un'interfaccia `ITelemetryClient` (di nuovo Dependency Inversion, come `ILLMClient` e `IRetriever`) che `ChatService` usa per segnalare eventi che contano per il business — non "una riga di log qualsiasi", ma cose tipo *"il retriever non ha trovato nulla di rilevante"* o *"quanto ha impiegato la chiamata ad Azure OpenAI"*
- **Query KQL** nel portale per rispondere a domande da supporto reale: "il bot sta rispondendo?", "con che latenza?", "ci sono eccezioni?"
- **Live Metrics**: monitoraggio in tempo reale, utile proprio per il tipo di verifica "post-deploy" che ti è mancata con la Fase 3

Nota architetturale: `ChatService` continuerà a non sapere nulla di "Application Insights" — dipenderà solo da `ITelemetryClient`, esattamente come non sa nulla di "Azure OpenAI" o "Azure AI Search". Interface Segregation + Dependency Inversion applicati in modo coerente su tutte le fasi.

---

## Step 1 — Verifica il collegamento esistente

1. Vai sulla tua Function App (`func-supportchatbot-don`) nel portale → menu laterale → **Application Insights**
2. Se vedi una risorsa già collegata (di solito con nome tipo `func-supportchatbot-don` o simile), è quella creata automaticamente quando hai fatto `az functionapp create` in Fase 1 — clicca per aprirla
3. Se non vedi nulla di collegato, clicca **Turn on Application Insights**, crea una nuova risorsa nella stessa region (Sweden Central o dove hai il resource group) e collegala

**Verifica anche l'app setting**, perché ti servirà a breve in locale: Function App → **Configuration** → **Application settings** → cerca `APPLICATIONINSIGHTS_CONNECTION_STRING` (o la vecchia `APPINSIGHTS_INSTRUMENTATIONKEY`). Se c'è, copia il valore — ti serve per il test in locale allo Step 5.

---

## Step 2 — `domain/interfaces.py`: aggiungi `ITelemetryClient`

```python
from abc import ABC, abstractmethod

class ITelemetryClient(ABC):
    """Astrazione per l'osservabilità. ChatService dipende da questa interfaccia,
    non da un SDK di monitoring specifico — se domani cambi provider
    (es. da Application Insights a un altro APM), ChatService non cambia."""

    @abstractmethod
    def track_event(self, name: str, properties: dict | None = None) -> None: ...

    @abstractmethod
    def track_exception(self, properties: dict | None = None) -> None: ...
```

---

## Step 3 — `infrastructure/app_insights_telemetry_client.py`

```python
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
```

---

## Step 4 — Istrumenta `ChatService`

`ChatService` riceve `ITelemetryClient` via constructor injection, come gli altri collaboratori. Adatta i nomi ai tuoi metodi reali se non coincidono esattamente:

```python
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
```

Punto per il colloquio: notare che il `try/except` non "gestisce" l'errore nel senso di nasconderlo — lo registra (`track_exception`) e poi lo rilancia (`raise`). La responsabilità di decidere come rispondere all'utente in caso di errore resta a un livello più esterno (l'handler HTTP in `function_app.py`), `ChatService` si occupa solo di logica di dominio + osservabilità del proprio comportamento.

---

## Step 5 — Collega tutto in `function_app.py` e testa in locale

```python
from infrastructure.app_insights_telemetry_client import AppInsightsTelemetryClient

telemetry = AppInsightsTelemetryClient()

chat_service = ChatService(
    llm_client=llm_client,       # già presente dalla Fase 2
    retriever=retriever,          # già presente dalla Fase 3
    telemetry=telemetry,
)
```

Prima di lanciare `func start`, aggiungi la connection string copiata allo Step 1 dentro `local.settings.json`:

```json
{
  "Values": {
    "APPLICATIONINSIGHTS_CONNECTION_STRING": "InstrumentationKey=...;IngestionEndpoint=..."
  }
}
```

`func start` → fai una domanda al bot → nel terminale locale non vedrai nulla di diverso (i log strutturati vanno ad App Insights, non stampano granché in più in console) — la vera verifica è nello Step 6.

---

## Step 6 — Interroga i log con KQL

Vai sulla risorsa Application Insights → **Logs**.

Nota sul portale reale (Microsoft ha aggiunto un layer AI sopra l'editor classico, stesso tipo di scostamento già visto con "Import data" in Fase 3):

1. Al primo apertura di **Logs** si apre un pannello chat **"Observability Agent"** invece dell'editor di query — in alto a destra c'è un toggle **"Agent"**: disattivalo per tornare all'editor classico.
2. Anche disattivato, l'editor si apre in **"Simple mode"** (controlli guidati: Select a table, Add filtro) e non in editor di testo libero — in alto a destra, apri il menu a tendina **"Simple mode"** e seleziona **"KQL mode"**: solo lì compare il riquadro dove incollare le query qui sotto.

Alcune query utili, da adattare mano a mano che vedi i nomi reali delle tue colonne:

**I tuoi eventi custom:**
```kql
traces
| where message in ("retrieval_empty", "llm_call_completed")
| order by timestamp desc
| take 50
```

**Latenza media e p95 delle chiamate a Azure OpenAI, a bucket di 5 minuti:**
```kql
traces
| where message == "llm_call_completed"
| extend duration_ms = todouble(customDimensions.duration_ms)
| summarize avg(duration_ms), percentile(duration_ms, 95) by bin(timestamp, 5m)
```

**Richieste HTTP verso `/api/chat` (telemetria automatica, senza codice custom):**
```kql
requests
| where name has "chat"
| project timestamp, resultCode, duration, success
| order by timestamp desc
```

**Eccezioni non gestite:**
```kql
exceptions
| order by timestamp desc
| take 20
```

---

## Step 7 — Ridistribuisci e osserva in Live Metrics

Redeploy come sempre (`Deploy to Function App` da VS Code). Poi, invece di lanciare Postman e sperare bene come con la Fase 3, apri **Application Insights → Live Metrics** *prima* di mandare la richiesta: vedrai la richiesta arrivare, il tempo di risposta e (dopo qualche secondo di latenza di ingestion) i tuoi eventi custom comparire nei Logs. Questa è la differenza pratica che avresti voluto avere un'ora fa.

Nota: Live Metrics funziona identico anche per i test in locale (basta che `local.settings.json` abbia la connection string vera, non il placeholder) — quindi puoi già usarlo ora con `func start`, prima ancora del redeploy vero e proprio, come prova generale.

**Come leggere il pannello "Sample telemetry"**: la maggior parte delle righe che vedrai sono rumore di infrastruttura generato dal runtime stesso, non dal tuo codice — in particolare `Ping Status: {"hostState": "Running"}` (heartbeat del host) e `Executing StatusCodeResult, setting HTTP status code 200` (Category `Microsoft.AspNetCore.Mvc.StatusCodeResult`, pipeline interna). Ignorale. Quello che ti interessa è una riga con **Message = `retrieval_empty`** o **`llm_call_completed`** — se non compare dopo una richiesta reale al bot, il problema è nel wiring di `ChatService`/`AppInsightsTelemetryClient`, non nel portale.

---

## Problemi incontrati e soluzioni

*(si popola mano a mano che procediamo — qui finiranno gli errori reali)*

| Errore | Causa | Soluzione |
|---|---|---|
| In **Logs** si apre un pannello chat "Observability Agent" invece dell'editor di query | Microsoft ha aggiunto un agente AI di default sopra l'editor KQL classico | Disattivare il toggle **"Agent"** in alto a destra |
| Anche con "Agent" disattivato, non c'è un riquadro dove scrivere KQL a mano — solo controlli guidati (Select a table, Add filtro) | L'editor si apre in **"Simple mode"**, la modalità guidata, non in modalità testo libero | Aprire il menu a tendina **"Simple mode"** in alto a destra e selezionare **"KQL mode"** |
| Query `traces` su `retrieval_empty`/`llm_call_completed` restituisce zero righe, ma `requests` funziona | `APPLICATIONINSIGHTS_CONNECTION_STRING` in `local.settings.json` era rimasta col placeholder letterale `InstrumentationKey=...;IngestionEndpoint=...` invece del valore reale — il codice locale non ha mai inviato nulla | Copiare il valore vero da Application Insights → Overview → campo "Connection String" (icona di copia), sostituendolo per intero nel file |
| In Live Metrics → Sample Telemetry si vedono solo righe tipo `Ping Status` e `Executing StatusCodeResult, setting HTTP status code 200` | Sono telemetria di infrastruttura generata dal runtime stesso (heartbeat del host, pipeline ASP.NET Core interna), non i propri eventi custom | Cercare una riga con Message uguale a `retrieval_empty` o `llm_call_completed` (Category legata al logger `chatbot.telemetry`) — se non compare dopo aver mandato una richiesta reale, il problema è nel wiring del codice, non nel portale |

---

## 🎯 Perché per il colloquio

- **"Come diagnostichi un chatbot che risponde lentamente in produzione?"** — risposta attesa: query KQL su `requests`/`traces` per isolare se il collo di bottiglia è il retrieval (Azure AI Search) o la generation (Azure OpenAI), invece di indovinare — esattamente la distinzione che i due eventi custom (`retrieval_empty` vs `llm_call_completed`) ti permettono di fare.
- **Logging vs. Telemetry vs. APM**: il logging è testo libero pensato per il debug umano; la telemetry (eventi/metriche strutturate) è pensata per essere interrogata e aggregata; Application Insights è l'APM (Application Performance Monitoring) che raccoglie entrambe insieme a dati automatici (richieste, dipendenze, eccezioni).
- **Checkpoint architetturale**: perché `ITelemetryClient` come interfaccia separata invece di chiamare `logging` direttamente da `ChatService`? Perché altrimenti `ChatService` dipenderebbe da un dettaglio infrastrutturale (il formato di `extra={"custom_dimensions": ...}` specifico di App Insights) — la stessa Dependency Inversion applicata per `ILLMClient` e `IRetriever`, applicata qui alla osservabilità.
- **Collegamento diretto con l'incidente di Fase 3**: sai già raccontare un esempio concreto e vissuto in prima persona di "come avresti individuato prima" un deploy disallineato — è oro per un colloquio su un ruolo di troubleshooting.
