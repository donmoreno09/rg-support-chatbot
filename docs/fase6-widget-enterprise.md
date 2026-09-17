# Fase 6 — Widget e sistema enterprise

> **Perché questa fase, proprio ora?** Finora il bot risponde sempre, anche quando l'indice di Azure AI Search non contiene nulla di rilevante — in quel caso il rischio è che l'LLM "inventi" una risposta plausibile ma sbagliata (allucinazione), perché riceve un contesto vuoto ma nessuno gli dice di fermarsi. In un sistema di supporto reale, non rispondere a vuoto è più importante che rispondere sempre: se il bot non sa, deve **escalare a un umano**, non improvvisare. Questa fase aggiunge quella rete di sicurezza (apertura ticket), più un piccolo front-end per parlare col bot senza passare da Postman.

---

## Prima: chiudiamo la Fase 5 con i commit

```bash
git add domain/interfaces.py
git commit -m "feat(domain): add IQueuePublisher interface"

git add infrastructure/azure_queue_publisher.py
git commit -m "feat(infrastructure): add AzureQueuePublisher"

git add function_app.py
git commit -m "feat(api): route complex messages to queue and add process_complex_query trigger"
```

---

## Cosa costruisci in questa Fase 6

- Una **nuova interfaccia** `ITicketService` (stessa Dependency Inversion vista in tutte le fasi precedenti): chi decide di aprire un ticket non deve sapere se dietro c'è un vero sistema enterprise (ServiceNow, Zendesk...) o, come qui, un webhook fittizio
- Una **implementazione concreta**, `WebhookTicketService`, che manda il ticket a [webhook.site](https://webhook.site) — un servizio gratuito che ti dà un URL usa-e-getta per vedere in tempo reale le richieste HTTP che arrivano
- Una **piccola ma reale modifica a `ChatService`**: se il retriever non trova contesto, invece di chiamare comunque l'LLM, apre un ticket e lo comunica all'utente
- Un **widget** HTML/JS minimale che parla con `/api/chat` da un browser
- La **configurazione CORS**, necessaria perché il widget (che gira su un'origine diversa) possa chiamare la Function App

### Nota architetturale — questa volta *modifichiamo* `ChatService`, non lo estendiamo

In Fase 5 avevamo rispettato l'Open/Closed Principle alla lettera: nuovo canale (coda), zero righe toccate in `ChatService`. Qui invece tocchiamo davvero il corpo di `handle()`. **Non è un'incoerenza**: l'OCP protegge il codice da modifiche quando cambi *come* un lavoro viene fatto o *da dove* arriva (HTTP vs coda, OpenAI vs un altro provider). Ma qui stiamo cambiando **la regola di business stessa** — cosa significhi "rispondere bene" include ora "sapere quando non rispondere". Questa non è un'estensione, è una correzione della logica di dominio, e va fatta lì. Sapere distinguere questi due casi (estendere vs correggere il cuore della logica) è esattamente il tipo di giudizio architetturale che un colloquio senior prova a valutare.

Nota anche un effetto collaterale gratuito: dato che sia l'endpoint HTTP sincrono sia `process_complex_query` (Fase 5) chiamano lo stesso `chat_service.handle()`, l'escalation funziona automaticamente su **entrambi** i canali, senza scrivere nulla in più.

---

## Step 1 — `domain/interfaces.py`: aggiungi `ITicketService`

```python
class ITicketService(ABC):
    """Astrazione per l'apertura di un ticket quando il bot non trova contesto
    sufficiente per rispondere con sicurezza. Chi la usa non sa se dietro c'è
    un vero sistema di ticketing enterprise o, come in questo progetto
    dimostrativo, un webhook fittizio — se domani cambia il sistema reale,
    non si tocca ChatService."""

    @abstractmethod
    def create_ticket(self, message: str, reason: str) -> str: ...
```

---

## Step 2 — Procurati un URL di test

Vai su **[webhook.site](https://webhook.site)** (nessuna registrazione richiesta): ti genera subito un URL univoco tipo `https://webhook.site/a1b2c3d4-...`. Tienilo aperto in una scheda del browser: ogni richiesta HTTP che gli mandi comparirà lì in tempo reale, con header e corpo — è il modo più veloce per "vedere" un ticket senza costruire un vero sistema di ticketing.

---

## Step 3 — `infrastructure/webhook_ticket_service.py`

```python
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
```

Aggiungi `requests` a `requirements.txt` se non c'è già (`pip install requests` nel venv attivo, poi `pip freeze` per controllare).

---

## Step 4 — Modifica `services/chat_service.py`

Ecco come diventa il tuo file reale (quello con la telemetria della Fase 4, che già rilevava `retrieval_empty` ma poi chiamava comunque l'LLM a vuoto):

```python
import time

from domain.interfaces import ILLMClient, IRetriever, ITelemetryClient, ITicketService


class ChatService:
    def __init__(
        self,
        llm_client: ILLMClient,
        retriever: IRetriever,
        telemetry: ITelemetryClient,
        ticket_service: ITicketService,
    ):
        self._llm_client = llm_client
        self._retriever = retriever
        self._telemetry = telemetry
        self._ticket_service = ticket_service

    def handle(self, message: str) -> str:
        context = self._retriever.retrieve(message)

        if not context:
            self._telemetry.track_event("retrieval_empty", {"query": message})
            ticket_id = self._ticket_service.create_ticket(
                message=message,
                reason="Nessun contesto trovato nella knowledge base",
            )
            self._telemetry.track_event(
                "escalated_to_ticket", {"query": message, "ticket_id": ticket_id}
            )
            return (
                f"Non ho trovato informazioni sufficienti per risponderti con "
                f"certezza. Ho aperto il ticket {ticket_id}: un operatore ti "
                f"contatterà a breve."
            )

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

Cosa cambia rispetto a prima, riga per riga:

- **Import**: aggiunto `ITicketService` dalla stessa riga di `domain.interfaces` — un solo import in più, nessuna nuova dipendenza esterna.
- **`__init__`**: un quarto parametro, `ticket_service: ITicketService`, salvato in `self._ticket_service` — stesso schema di `telemetry` in Fase 4, nessuna sorpresa.
- **Il blocco `if not context:`** esisteva già (Fase 4) e loggava `retrieval_empty`, ma poi il flusso **proseguiva** verso `self._llm_client.complete(message, context)` con un contesto vuoto — l'LLM veniva chiamato comunque, col rischio di allucinare. Ora, dentro quello stesso `if`, apriamo il ticket e facciamo **`return` immediato**: il resto della funzione (chiamata LLM, timing, secondo evento di telemetria) non viene più eseguito in questo caso.
- **`self._telemetry.track_event("escalated_to_ticket", ...)`** è un secondo evento, distinto da `retrieval_empty`: il primo dice "il retriever non ha trovato nulla", il secondo dice "e di conseguenza abbiamo aperto un ticket" — separarli ti permette, su Application Insights, di contare quante ricerche vuote diventano davvero un ticket (sempre, con questa logica) rispetto a quante ne trovi in totale.
- **Il blocco `start = time.monotonic()` / `try` / `except` / timing** resta identico a come l'avevi — ma ora gira **solo** quando c'è davvero una chiamata all'LLM da misurare. Prima with `context` vuoto avresti comunque misurato una chiamata reale (ma inutile) all'LLM; ora quel ramo semplicemente non viene raggiunto.

`if not context:` funziona perché `context` è una lista: una lista vuota (`[]`) è "falsy" in Python, cioè si comporta come `False` in un `if` — non serve scrivere `if len(context) == 0:`, anche se è equivalente ed esplicito se lo trovi più chiaro.

> **Nota realistica**: con questa regola grezza, anche un messaggio tipo "ciao" (che non troverà mai contesto in una FAQ tecnica) finisce per aprire un ticket. In un sistema vero affineresti la regola — es. uno score minimo di rilevanza restituito dal retriever, o un controllo di intent separato prima del retrieval. Per questa fase va bene così: l'obiettivo è il meccanismo (interfaccia + escalation), non la sofisticazione della regola.

---

## Step 5 — Wiring in `function_app.py`

Rispetto al tuo file attuale, cambiano solo tre punti — nessun altro codice va toccato (route, threshold, `process_complex_query` restano identici).

**1. Un nuovo import**, insieme agli altri `infrastructure.*`:

```python
from infrastructure.webhook_ticket_service import WebhookTicketService
```

**2. Costruisci il `ticket_service`**, subito prima di `chat_service` (dove già costruisci `retriever` e `telemetry`):

```python
ticket_service = WebhookTicketService(
    webhook_url="https://webhook.site/IL-TUO-ID-UNIVOCO",  # quello copiato allo Step 2
)
```

**3. Passa `ticket_service` a `ChatService`.** Il tuo `chat_service` attuale è su una riga sola:

```python
chat_service = ChatService(retriever=retriever, llm_client=AzureOpenAIClient(
    endpoint="https://oai-support-chatbot.openai.azure.com/", deployment="chat-deploy"), telemetry=telemetry,)
```

diventa (spezzato su più righe solo per leggibilità — non è obbligatorio, ma con quattro argomenti inizia a essere più chiaro così):

```python
chat_service = ChatService(
    retriever=retriever,
    llm_client=AzureOpenAIClient(
        endpoint="https://oai-support-chatbot.openai.azure.com/",
        deployment="chat-deploy",
    ),
    telemetry=telemetry,
    ticket_service=ticket_service,
)
```

Nota: `EchoLLMClient` ed `EmptyRetriever` restano lì come codice morto (non li usa più nessuno dalla Fase 2/3) — se vuoi puoi rimuoverli ora, ma non è richiesto per questa fase.

---

## Step 5bis — Correggi il retriever: senza questo, l'escalation non scatta mai

Se testi subito lo Step 6, probabilmente scopri che il ticket **non** si apre nemmeno per domande completamente fuori tema (es. "qual è la ricetta della carbonara?"): l'LLM risponde comunque, a volte anche onestamente ("non trovo questa informazione nel contesto"), ma `ChatService` non prende il ramo di escalation. Il problema è a monte, in `infrastructure/azure_search_retriever.py`.

**Causa**: la ricerca ibrida (`search_text=query` insieme a `vector_queries=[...]`) usa **RRF (Reciprocal Rank Fusion)** per calcolare `@search.score`. RRF misura solo la *posizione in classifica* (1°, 2°, 3°...), non quanto un risultato sia davvero pertinente. Con `top=3` ottieni sempre 3 punteggi ravvicinati — anche quando nessuno dei 3 risultati è realmente rilevante — quindi `retrieve()` non torna mai `[]` e `if not context:` in `ChatService` non scatta mai.

**Correzione**: togli la componente keyword (`search_text=None`) così `@search.score` torna a essere la similarità coseno pura (0–1, interpretabile), poi filtra per una soglia minima misurata sui tuoi dati reali — non indovinata a tavolino:

```python
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
        results = self._client.search(
            search_text=None,          # niente keyword: score = similarità coseno pura
            vector_queries=[vector_query],
            top=3,
        )
        return [
            r["chunk"] for r in results
            if r["@search.score"] >= self._score_threshold
        ]
```

`score_threshold` ha un default, quindi nessuna modifica richiesta in `function_app.py`.

**Come è stata trovata la soglia `0.60`** (procedimento da ripetere se cambi indice o modello di embedding, non un numero universale):

1. Logga temporaneamente `@search.score` per ogni chunk (`logging.info(f"score={r['@search.score']:.4f} chunk={r['chunk'][:40]!r}")`), **prima** del filtro
2. Manda da Postman una domanda presente nella FAQ → annota i 3 punteggi
3. Manda una domanda completamente fuori tema → annota i 3 punteggi
4. Scegli la soglia a metà tra il più basso del gruppo pertinente e il più alto del gruppo fuori tema
5. Rimuovi il logging di debug, imposta la soglia trovata, ritesta entrambe le domande

> 🪤 **Trappola da colloquio**: "uso lo score di una ricerca ibrida RRF per filtrare i risultati irrilevanti" è un errore comune — RRF è pensato per *ordinare* risultati, non per *giudicare la qualità assoluta* di un match. Per un filtro di rilevanza serve lo score della sola ricerca vettoriale (similarità coseno), che è quello che questa correzione ripristina passando `search_text=None`.

---

## Step 6 — Testa l'escalation (prima del widget)

1. `func start` (Azurite acceso come sempre)
2. Da Postman, manda un messaggio che di sicuro **non** è nel tuo indice FAQ (es. `"qual è la ricetta della carbonara?"`)
3. Aspettati una risposta `200` con un `reply` che menziona un ticket aperto
4. Controlla la scheda del browser con webhook.site: dovrebbe comparire una nuova richiesta `POST` con `ticket_id`, `message` e `reason`
5. Manda anche una domanda che **è** nel tuo indice → verifica che il flusso normale (Fase 3/4) continui a rispondere come prima, senza ticket

---

## Step 7 — Crea `widget/chat-widget.html`

```html
<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <title>Support Chatbot</title>
  <style>
    body { font-family: sans-serif; max-width: 480px; margin: 40px auto; }
    #chat-box { border: 1px solid #ccc; padding: 12px; height: 320px; overflow-y: auto; margin-bottom: 8px; }
    #chat-box p { margin: 4px 0; }
    #chat-input { width: 75%; padding: 6px; }
    button { padding: 6px 12px; }
  </style>
</head>
<body>
  <h3>Support Chatbot</h3>
  <div id="chat-box"></div>
  <input id="chat-input" type="text" placeholder="Scrivi un messaggio...">
  <button onclick="sendMessage()">Invia</button>

  <script>
    const FUNCTION_URL = "http://localhost:7071/api/chat"; // cambia con l'URL pubblico dopo il deploy

    async function sendMessage() {
      const input = document.getElementById("chat-input");
      const text = input.value.trim();
      if (!text) return;
      appendMessage("Tu", text);
      input.value = "";

      try {
        const res = await fetch(FUNCTION_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text })
        });
        const data = await res.json();
        appendMessage("Bot", data.reply ?? `Richiesta accettata (id: ${data.request_id})`);
      } catch (err) {
        appendMessage("Errore", "Impossibile contattare il bot: " + err.message);
      }
    }

    function appendMessage(sender, text) {
      const box = document.getElementById("chat-box");
      box.innerHTML += `<p><strong>${sender}:</strong> ${text}</p>`;
      box.scrollTop = box.scrollHeight;
    }
  </script>
</body>
</html>
```

`data.reply ?? ...` usa l'operatore JavaScript "nullish coalescing": se `data.reply` è `undefined` (caso del ramo asincrono della Fase 5, che risponde con `request_id` invece che `reply`), mostra il messaggio alternativo.

---

## Step 8 — Servi il widget da un vero server locale (non aprirlo come file)

Se apri `chat-widget.html` con doppio click (`file://...`), il browser tratta la pagina come un'origine speciale `null`, e molte configurazioni CORS la rifiutano per default. Più semplice e realistico: servilo da un mini server HTTP.

```bash
cd widget
python -m http.server 5500
```

Poi apri `http://localhost:5500/chat-widget.html` nel browser.

---

## Step 9 — Configura CORS

Il browser blocca per default le chiamate `fetch` verso un'origine diversa da quella che ha servito la pagina (`http://localhost:5500` → `http://localhost:7071` sono origini diverse: porta diversa = origine diversa). Il server (la tua Function App) deve dichiarare esplicitamente "accetto richieste anche da quest'altra origine".

**In locale**, apri `local.settings.json` e aggiungi una sezione `Host` allo stesso livello di `Values`:

```json
{
  "IsEncrypted": false,
  "Values": { ... },
  "Host": {
    "CORS": "*",
    "CORSCredentials": false
  }
}
```

`"*"` per ora va bene (ambiente di sviluppo); in produzione elencheresti solo gli origin reali del widget. Riavvia `func start` perché la modifica sia letta.

**Su Azure** (quando farai il deploy), stessa cosa via CLI:

```bash
az functionapp cors add --name <la-tua-function-app> --resource-group <il-tuo-rg> --allowed-origins "*"
```

---

## Step 10 — Test end-to-end

1. `func start` (con Azurite e la sezione `Host.CORS` attiva)
2. `python -m http.server 5500` dentro `widget/`
3. Apri `http://localhost:5500/chat-widget.html`
4. Scrivi una domanda presente nell'indice FAQ → aspettati una risposta normale
5. Scrivi qualcosa fuori tema → aspettati il messaggio di ticket, e verifica su webhook.site che la richiesta sia arrivata

---

## Problemi incontrati e soluzioni

*(si popola mano a mano che procediamo — qui finiranno gli errori reali)*

| Errore | Causa | Soluzione |
|---|---|---|
| Il ticket non si apre mai, nemmeno per domande completamente fuori tema | Il retriever fa ricerca ibrida (keyword + vettore): lo score RRF risultante misura solo il rank, non la rilevanza reale — `context` non è mai `[]` | Vedi Step 5bis: `search_text=None` per uno score di similarità coseno interpretabile, poi filtra per soglia misurata |
| `Access to fetch at 'http://localhost:7071/...' has been blocked by CORS policy` | Manca la sezione `Host.CORS` in `local.settings.json`, o `func start` non è stato riavviato dopo averla aggiunta | Aggiungi la sezione, riavvia `func start` |
| Il ticket non compare su webhook.site | URL sbagliato in `webhook_url`, oppure `requests` non installato nel venv | Ricontrolla l'URL copiato allo Step 2; `pip install requests` |
| Il widget mostra "Failed to fetch" | `func start` non è in esecuzione, o `FUNCTION_URL` punta alla porta sbagliata | Verifica che il terminale di `func start` sia attivo sulla `:7071` |
| — | — | — |

---

## 🎯 Perché per il colloquio

- **"Come eviti che il bot inventi risposte quando non ha informazioni?"** — risposta attesa: controllo esplicito sul contesto restituito dal retriever, con escalation a un processo umano (ticket) invece di una risposta generata a vuoto — è un pattern comune nei sistemi RAG di produzione, non solo un dettaglio di questo progetto.
- **Estendere vs correggere il dominio**: sapere spiegare perché qui è corretto modificare `ChatService` (regola di business nuova), mentre in Fase 5 era corretto non toccarlo (nuovo canale di trasporto), mostra di aver capito l'OCP nella sostanza e non solo come slogan.
- **Dependency Inversion ancora una volta**: `ITicketService` è il quinto contratto di questo tipo nel progetto (`ILLMClient`, `IRetriever`, `ITelemetryClient`, `IQueuePublisher`, ora questo) — un pattern ripetuto consapevolmente, non un caso isolato: è quello che rende il sistema testabile e sostituibile pezzo per pezzo.
- **CORS**: sapere spiegarlo a parole povere — è una protezione del *browser*, non del server, pensata per impedire che uno script su un sito malevolo usi silenziosamente le credenziali dell'utente per chiamare API di un altro sito. Il server deve "autorizzare" esplicitamente le origini che vuole accettare.
- **Riuso tra canali**: l'escalation funziona automaticamente anche sul percorso asincrono di Fase 5, perché entrambi chiamano lo stesso `chat_service.handle()` — la stessa dimostrazione di "logica scritta una volta sola" vista nella fase precedente.
