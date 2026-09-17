# Fase 5 — Elaborazione asincrona (simulando una Change Request)

> **Perché questa fase, proprio ora?** Finora il flusso è sempre stato sincrono: l'utente manda un messaggio, il bot chiama Azure AI Search e Azure OpenAI, e solo alla fine risponde — l'utente resta in attesa per tutta la durata. Per una domanda semplice va bene. Ma se un giorno il retrieval è lento, o serve un'elaborazione più pesante (es. generare un report, coinvolgere un sistema esterno), tenere l'utente bloccato su una singola richiesta HTTP diventa un problema reale. Questa fase introduce il pattern che risolve il problema: **rispondi subito, elabora dopo**, senza toccare una riga del flusso già esistente.

---

## Prima: chiudiamo la Fase 4 con i commit

Stessa logica delle fasi precedenti — un commit per layer:

```bash
git add domain/interfaces.py
git commit -m "feat(domain): add ITelemetryClient interface"

git add infrastructure/app_insights_telemetry_client.py
git commit -m "feat(infrastructure): add AppInsightsTelemetryClient"

git add services/chat_service.py
git commit -m "feat(services): instrument ChatService with telemetry events"

git add function_app.py
git commit -m "feat(api): wire AppInsightsTelemetryClient into ChatService"
```

---

## Cosa costruisci in questa Fase 5

- Una **coda** (`complex-queries`) sullo Storage Account già esistente — una lista di messaggi in attesa di essere processati
- Una **nuova interfaccia** `IQueuePublisher` (stessa Dependency Inversion di `ILLMClient`, `IRetriever`, `ITelemetryClient`): chi decide di instradare una richiesta in coda non deve sapere nulla dei dettagli di Azure Storage
- Una **seconda Azure Function**, `process_complex_query`, attivata dalla coda invece che da HTTP — riusa `ChatService` così com'è, **zero duplicazione di logica**
- Una piccola regola di classificazione nell'endpoint `/api/chat`: se la richiesta è "complessa" (per ora: lunghezza del messaggio), va in coda invece che processata subito

Nota architetturale: questo è l'**Open/Closed Principle** applicato a livello di architettura — estendi il comportamento del sistema (un secondo canale di elaborazione) **aggiungendo** una function nuova, senza **modificare** `ChatService` né l'endpoint HTTP esistente. Il codice esistente resta chiuso alla modifica, il sistema è aperto all'estensione.

---

## Step 1 — Crea la coda

1. Vai sul tuo Storage Account (creato automaticamente in Fase 1, stesso resource group — nome tipo `supportchatbotXXXX`)
2. Menu laterale → **Queues** → **+ Queue** → nome `complex-queries`
3. Assicurati che **Azurite** sia acceso in locale (stesso comando `azurite` della Fase 1, in un terminale a parte) — la coda locale è separata da quella su Azure, e senza Azurite attivo il trigger non parte mai in `func start`

---

## Step 2 — `domain/interfaces.py`: aggiungi `IQueuePublisher`

```python
from abc import ABC, abstractmethod

class IQueuePublisher(ABC):
    """Astrazione per instradare un lavoro verso elaborazione asincrona.
    L'endpoint HTTP dipende da questa interfaccia, non da come Azure Storage
    Queue funziona nel dettaglio — se domani cambi meccanismo (es. Service Bus),
    non tocchi function_app.py."""

    @abstractmethod
    def publish(self, message: dict) -> None: ...
```

---

## Step 3 — `infrastructure/azure_queue_publisher.py`

In Azure Functions Python v2 il modo idiomatico di scrivere su una coda è un **output binding**, non una chiamata SDK manuale — il runtime gestisce la connessione per te (stessa identità/connection string già configurata).

```python
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
```

---

## Step 4 — Modifica l'endpoint `/api/chat`

Aggiungi l'output binding verso la coda e la regola di instradamento. Adatta i nomi ai tuoi parametri reali se non coincidono esattamente:

```python
import uuid
import azure.functions as func

from services.chat_service import ChatService
from infrastructure.azure_queue_publisher import AzureQueuePublisher

COMPLEXITY_THRESHOLD = 200  # caratteri — soglia arbitraria, solo per simulare il caso


@app.route(route="chat", methods=["POST"])
@app.queue_output(arg_name="queueMsg", queue_name="complex-queries",
                   connection="AzureWebJobsStorage")
def chat_endpoint(req: func.HttpRequest, queueMsg: func.Out[str]) -> func.HttpResponse:
    body = req.get_json()
    message = body.get("message", "")

    if len(message) > COMPLEXITY_THRESHOLD:
        request_id = str(uuid.uuid4())
        publisher = AzureQueuePublisher(queueMsg)
        publisher.publish({"request_id": request_id, "message": message})
        return func.HttpResponse(
            json.dumps({"status": "accepted", "request_id": request_id}),
            status_code=202,
            mimetype="application/json",
        )

    reply = chat_service.handle(message)
    return func.HttpResponse(
        json.dumps({"reply": reply}), mimetype="application/json"
    )
```

`202 Accepted` significa "ho ricevuto la richiesta e la sto processando, ma non è ancora finita" — diverso da `200`, che implica una risposta già pronta nel corpo.

**Perché `@app.route` sta sopra `@app.queue_output`, e non il contrario:** i decoratori si applicano dal basso verso l'alto. `@app.queue_output` (il più vicino alla funzione) si applica per primo e "attacca" il binding extra; `@app.route` si applica per ultimo e **finalizza e registra** la funzione completa presso `app` — deve quindi vedere già tutti i binding attaccati. Il trigger (qui `@app.route`) va sempre in cima; qualunque binding aggiuntivo (come `@app.queue_output`) va sotto.

---

## Step 5 — Crea la function attivata dalla coda

```bash
func new
```

Scegli **Azure Queue Storage trigger**, nome `process_complex_query`, coda `complex-queries`. Quando chiede la connection string, scrivi il **nome** della app setting che la contiene — `AzureWebJobsStorage` — non una stringa da comporre a mano: è la stessa già usata per l'output binding dello Step 4.

**Dove va a finire il codice:** con il modello di programmazione v2 (quello che stai usando fin dalla Fase 1 — un solo `app = func.FunctionApp()` condiviso), `func new` non crea un file separato: **aggiunge la function direttamente in fondo a `function_app.py`**, lo stesso file dove vive già `chat`. Non spostarla altrove — tutte le function di questo progetto convivono in quel file, registrate sullo stesso oggetto `app`.

Apri `function_app.py`, scorri fino in fondo: troverai uno scheletro generato tipo

```python
@app.queue_trigger(arg_name="msg", queue_name="complex-queries",
                    connection="AzureWebJobsStorage")
def process_complex_query(msg: func.QueueMessage):
    logging.info('Python Queue trigger processed a message: %s',
                 msg.get_body().decode('utf-8'))
```

**Sostituisci quel corpo generato** con la versione collegata al progetto:

```python
@app.queue_trigger(arg_name="msg", queue_name="complex-queries",
                    connection="AzureWebJobsStorage")
def process_complex_query(msg: func.QueueMessage) -> None:
    payload = json.loads(msg.get_body().decode("utf-8"))
    request_id = payload["request_id"]
    message = payload["message"]

    reply = chat_service.handle(message)  # identica logica dell'endpoint sincrono

    logging.info(
        "complex_query_completed",
        extra={"custom_dimensions": {"request_id": request_id, "reply_length": len(reply)}},
    )
    # Qui in un sistema reale salveresti il risultato da qualche parte
    # (es. Cosmos DB, un'altra coda di risposta) associato a request_id.
```

Nota: `chat_service` qui è lo **stesso oggetto** costruito una volta in `function_app.py` con `llm_client`, `retriever` e `telemetry` già iniettati — nessuna nuova istanza, nessuna logica duplicata tra i due punti di ingresso (HTTP e coda).

**Controlla gli import in cima al file**: `func new` a volte aggiunge lo scheletro senza toccare gli import esistenti. `json` e `func` (cioè `azure.functions`) li hai già dalla Fase 1. Se manca `import logging`, aggiungilo tu a mano in cima a `function_app.py` — serve per la riga `logging.info(...)` dentro `process_complex_query`.

---

## Step 6 — Testa in locale

1. Avvia Azurite in un terminale separato
2. `func start`
3. Manda una richiesta con un messaggio molto lungo (oltre `COMPLEXITY_THRESHOLD`) via Postman → aspettati `202` con un `request_id`
4. Nei log del terminale dovresti vedere `process_complex_query` attivarsi da sola pochi istanti dopo, senza che tu l'abbia chiamata direttamente
5. Manda anche un messaggio corto → verifica che il flusso sincrono di sempre continui a funzionare esattamente come prima

**Verifica anche su Application Insights** (non serve aver deployato — se `APPLICATIONINSIGHTS_CONNECTION_STRING` è già in `local.settings.json` dalla Fase 4, `func start` in locale manda comunque telemetria vera alla risorsa su Azure):

```kql
requests
| where name in ("chat", "process_complex_query")
| project timestamp, name, success, resultCode, duration
| order by timestamp desc
```

Dovresti vedere due righe distinte per lo stesso test: una per `chat` (con `resultCode = 202`) e una per `process_complex_query` pochi istanti dopo. Per confermare che l'elaborazione è arrivata fino in fondo:

```kql
traces
| where message == "complex_query_completed"
| order by timestamp desc
```

**Attenzione con l'URL pubblico**: finché non fai il redeploy, `https://<la-tua-function-app>.azurewebsites.net/api/chat` esegue ancora il codice della Fase 4 — nessun `COMPLEXITY_THRESHOLD`, nessuna coda, sempre `200`. La coda `complex-queries` è comunque già pronta su Azure (l'hai creata manualmente allo Step 1), quindi quando farai `Deploy to Function App` non dovrai toccare nulla lato infrastruttura.

---

## Problemi incontrati e soluzioni

*(si popola mano a mano che procediamo — qui finiranno gli errori reali)*

| Errore | Causa | Soluzione |
|---|---|---|
| "Unable to access AzureWebJobsStorage" | Azurite non acceso | Avvialo in un terminale a parte prima di `func start` |
| `process_complex_query` non si attiva mai | Il nome della coda nel decoratore non combacia esattamente con quello creato (incluse maiuscole/minuscole) | Controlla che `queue_name` sia identico in entrambi i punti |
| "Queue Name is not valid" durante `func new` | I nomi delle code su Azure Storage accettano solo lettere minuscole, numeri e trattini — non l'underscore | Usa `complex-queries`, non `complex_queries` |
| — | — | — |

---

## 🎯 Perché per il colloquio

- **"Come gestiresti una richiesta che rischia di far scadere il timeout HTTP?"** — risposta attesa: pattern di disaccoppiamento sincrono/asincrono via coda, `202 Accepted` con un `request_id` che il client può usare per fare polling o essere notificato dopo.
- **Open/Closed Principle applicato architetturalmente**: hai esteso il sistema con un nuovo canale di elaborazione aggiungendo codice, non modificando `ChatService` né l'endpoint esistente.
- **Riuso vs. duplicazione**: `process_complex_query` non reimplementa la logica di business — chiama lo stesso `ChatService` dell'endpoint sincrono. Un errore comune in progetti reali è duplicare la logica "per velocità" tra i due entry point, creando due comportamenti che divergono nel tempo.
- **Perché un'interfaccia (`IQueuePublisher`) anche per una coda**: stessa Dependency Inversion vista in tutte le fasi precedenti — l'endpoint HTTP dipende da un contratto astratto, non dai dettagli di Azure Storage Queue. Se domani il sistema enterprise di Fase 6 richiedesse Service Bus invece di Storage Queue, cambieresti solo l'implementazione.
