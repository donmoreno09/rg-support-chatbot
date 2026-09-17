# Assistente di Supporto Tecnico RAG-based — Guida (Fase 0 e Fase 1)

Un chatbot di supporto che indicizza documentazione interna, risponde con Azure OpenAI usando RAG per il grounding, ed esegue escalation verso un sistema di ticketing quando non trova la risposta.

> ✅ Ogni fase include i passi concreti, il codice completo (non solo estratti), una traccia di "cosa succede quando arriva una richiesta", e una tabella degli errori più comuni con causa e soluzione.

## Copertura dei requisiti

Ogni riga dell'annuncio mappata su una fase concreta del progetto completo (questo documento copre solo Fase 0 e Fase 1).

| Requisito dall'annuncio | Fase |
|---|---|
| Conoscenza della piattaforma Microsoft Azure | Fase 0 |
| Azure Functions | Fase 1, Fase 5 |
| Application Insights | Fase 4 |
| Azure OpenAI | Fase 2 |
| Python | Trasversale |
| API REST | Fase 1 |
| Implementazione soluzioni RAG | Fase 3 |
| Gestione sottoscrizioni/consumi (PTU) | Fase 7 |
| Integrazione widget e sistemi enterprise | Fase 6 |
| Nice to have — Copilot Studio | Fase 8 |
| Nice to have — NLU / CLU | Fase 8 |

## Architettura d'insieme

Il flusso principale: **Widget (HTML/JS)** → **API Function (HTTP trigger, `/api/chat`)** → **Chat Service** (orchestrazione) → **Azure AI Search** (retrieval RAG) + **Azure OpenAI** (chat completion) → **Cosmos DB** (stato conversazione).

Un ramo asincrono separato: **Queue Function** (escalation) → **Ticket System** (stub enterprise).

**Application Insights** osserva l'intera pipeline senza bloccarla, raccogliendo telemetria da ogni componente.

## Prerequisiti — strumenti da installare

Un'unica volta, prima della Fase 0. Se hai già qualcosa di questo elenco, salta pure quel punto.

1. **Python 3.11.** Vai su `python.org/downloads`, scarica l'installer. Su Windows spunta "Add Python to PATH" durante l'installazione. Verifica:
   ```bash
   python --version
   ```
2. **Visual Studio Code.** Da `code.visualstudio.com`.
3. **Estensione "Azure Functions" per VS Code.** Pannello Extensions (icona a quadrati) → cerca "Azure Functions" → Install.
4. **Node.js** (serve solo per il passo successivo). Da `nodejs.org`, versione LTS.
5. **Azure Functions Core Tools** — fa girare le Function sul tuo computer prima di pubblicarle.
   ```bash
   npm install -g azure-functions-core-tools@4 --unsafe-perm true
   ```
6. **Azure CLI** — poi autenticati:
   ```bash
   az login
   ```
7. **Azurite** — emula lo storage di Azure sul tuo computer.
   ```bash
   npm install -g azurite
   ```
8. **Un account Azure attivo** con subscription pay-as-you-go o crediti gratuiti (`azure.microsoft.com/free`).
9. **Postman** (opzionale) da `postman.com/downloads`, per testare l'API con un'interfaccia grafica.

`local.settings.json` conterrà i tuoi segreti in locale — va nel `.gitignore`, non si committa mai. In Azure niente API key in chiaro: userai Managed Identity.

---

## Fase 0 — Fondamenta Azure

Prepari il terreno prima di scrivere codice: un resource group dedicato, un Key Vault, e un budget alert.

### Come si fa, passo dopo passo

1. **Crea il Resource Group.** Vai su `portal.azure.com` e fai login. Cerca "Resource groups" → **+ Create**. Subscription tua, nome `rg-support-chatbot-dev`, region "West Europe". **Review + create** → **Create**.
   *Un Resource Group è solo un contenitore logico: raggruppa le risorse del progetto così puoi vederle, gestirle ed eliminarle tutte insieme.*
2. **Crea il Key Vault.** Cerca "Key Vault" → **+ Create**. Resource group appena creato, nome univoco globale (es. `kv-supportchatbot-don`), region uguale, pricing tier "Standard". **Review + create** → **Create**.
3. **Imposta un budget di sicurezza.** Cerca "Cost Management + Billing" → **Budgets** → **+ Add**. Scope: la subscription. Importo (es. 20€/mese). Avviso email all'80% e al 100%. Salva.

### Cosa costruisci in questa fase

Nessun codice qui, ma tre fondamenta su cui si appoggia tutto il resto: il **Resource Group** è il contenitore che terrà insieme ogni risorsa del progetto, comodo per vederle e cancellarle tutte insieme a fine esperimento; il **Key Vault** è pronto per il giorno in cui servirà davvero un segreto (oggi non ne abbiamo ancora nessuno, perché tutto quello che costruiremo userà Managed Identity al suo posto); il **budget alert** è la rete di sicurezza per tutte le fasi successive, incluse quelle che costano davvero qualcosa (Azure OpenAI in Fase 2).

### Problemi comuni

| Errore | Causa | Soluzione |
|---|---|---|
| "Name not available" | Il nome del Key Vault deve essere univoco su *tutto* Azure, non solo nel tuo account | Aggiungi un suffisso personale o numerico al nome |
| "You do not have permissions..." | Il tuo utente non ha un ruolo sufficiente sulla subscription | Serve almeno il ruolo Contributor — chiedi a chi gestisce la subscription se non l'hai |

### Checklist

- [ ] Resource Group creato
- [ ] Key Vault creato
- [ ] Budget alert attivo

> **🎯 Perché per il colloquio**
> Organizzare le risorse in modo governabile — non solo farle "funzionare" — è esattamente ciò che serve nel troubleshooting quotidiano su un chatbot già in produzione.

> **Checkpoint**
> Sapresti spiegare perché il budget alert va impostato *prima* di creare risorse costose, non dopo?

---

## Fase 1 — Scaffold della Function e endpoint REST (Azure Functions · API REST · Python)

Crei l'endpoint `/api/chat` con il modello Python v2, strutturato a livelli fin da subito: la function fa solo da adapter HTTP, la logica vive in `ChatService`, che dipende da astrazioni e non da Azure direttamente.

### Come si fa, passo dopo passo

1. **Crea la cartella del progetto e aprila in VS Code.**
   ```bash
   mkdir support-chatbot
   cd support-chatbot
   code .
   ```
2. **Apri il terminale integrato.** Terminal → New Terminal.
3. **Crea e attiva un ambiente virtuale.** Una "bolla" isolata dove installare i pacchetti solo per questo progetto.
   ```bash
   python -m venv .venv
   ```
   ```bash
   # macOS / Linux
   source .venv/bin/activate

   # Windows (PowerShell)
   .venv\Scripts\Activate.ps1
   ```
   *Se ha funzionato, vedi `(.venv)` all'inizio della riga del terminale.*
4. **Inizializza il progetto Function.**
   ```bash
   func init . --python -m V2
   ```
   *Crea `host.json`, `requirements.txt`, `.funcignore` e `local.settings.json`. `-m V2` sceglie il modello moderno a decoratori — niente più cartella-per-funzione con `function.json` separato (quello era il vecchio modello v1).*
5. **Scrivi subito `local.settings.json`.** Viene creato vuoto (0 byte) e questo causa un warning finché non lo riempi — meglio farlo ora che scoprirlo più avanti. Apri il file e sostituisci tutto con:
   ```json
   {
     "IsEncrypted": false,
     "Values": {
       "AzureWebJobsStorage": "UseDevelopmentStorage=true",
       "FUNCTIONS_WORKER_RUNTIME": "python"
     }
   }
   ```
   *`AzureWebJobsStorage` dice al runtime dove tenere il proprio bookkeeping interno (trigger, code, timer). `UseDevelopmentStorage=true` punta ad Azurite, che avvieremo tra poco — così in locale non serve uno storage account Azure vero.*
6. **Crea la function HTTP-triggered.**
   ```bash
   func new
   ```
   *È interattivo: scegli **HTTP trigger**, nome `chat`, poi ti chiede l'**Auth Level** — tre opzioni: `FUNCTION` (richiede una chiave segreta nell'URL), `ANONYMOUS` (nessuna chiave, chiunque conosca l'URL può chiamarlo), `ADMIN` (master key, privilegi amministrativi). Scegli **ANONYMOUS**: il widget della Fase 6 chiamerà l'endpoint direttamente dal browser, e una function key incollata nel JavaScript sarebbe comunque visibile a chiunque apra la Console — quindi non offrirebbe protezione reale. La sicurezza vera la mettiamo altrove (CORS, eventualmente API Management).*
7. **Crea le cartelle `domain/` e `services/` nella root del progetto** — allo stesso livello di `function_app.py`, *non* dentro una sottocartella tipo `src/`. Dentro ciascuna crea anche un file vuoto `__init__.py`: dice a Python che quella cartella è un package importabile.
8. **Scrivi `domain/interfaces.py`** col codice sotto.
9. **Scrivi `services/chat_service.py`** col codice sotto.
10. **Sostituisci tutto `function_app.py`** (quello generato da `func new`, con dentro il codice di esempio) col codice completo sotto.
11. **Avvia Azurite in un secondo terminale** (lasciandolo acceso in background — non chiuderlo mentre sviluppi):
    ```bash
    azurite
    ```
12. **Torna al terminale principale**, verifica di essere nella **root** del progetto (quella con `host.json` dentro — usa `dir` su Windows o `ls` su macOS/Linux per controllare), poi:
    ```bash
    func start
    ```
13. **Testa l'endpoint.**
    ```bash
    # macOS / Linux
    curl -X POST http://localhost:7071/api/chat \
      -H "Content-Type: application/json" \
      -d '{"message":"ciao"}'

    # Windows (cmd/PowerShell — le virgolette interne vanno "escapate")
    curl -X POST http://localhost:7071/api/chat -H "Content-Type: application/json" -d "{\"message\":\"ciao\"}"
    ```
    Oppure con Postman: **New → HTTP Request** → metodo **POST** → incolla l'URL → tab **Body → raw → JSON** → `{"message": "ciao"}` → **Send**.
14. **Crea la Function App su Azure.** Qui la strada dipende dal tipo di subscription che hai:
    - Con una subscription **pay-as-you-go**, puoi usare il wizard grafico: pannello Azure di VS Code → sotto "Resources" → tasto destro sulla subscription → **Create Function App in Azure (Advanced)**.
    - Con una subscription **Free Trial** (la più comune per chi inizia), quel wizard — e anche il portale — propongono di default il piano **Flex Consumption**, che *non è supportato* sulle Free Trial: otterresti l'errore "Free trial subscription is not supported for Flex Consumption". In questo caso crea la Function App via **Azure CLI**, che usa il piano classico "Consumption" (supportato anche su Free Trial):

    ```bash
    # 1. Storage account (nome univoco, solo minuscole/numeri, max 24 caratteri)
    az storage account create --name stsupportchatbotdon --resource-group rg-support-chatbot-dev --location eastus --sku Standard_LRS

    # 2. Function App, piano Consumption classico, Linux, Python
    az functionapp create --resource-group rg-support-chatbot-dev --consumption-plan-location eastus --runtime python --runtime-version 3.11 --functions-version 4 --name func-supportchatbot-don --storage-account stsupportchatbotdon --os-type Linux
    ```
    *La tile "Consumption (Windows)" del portale non fa mai comparire Python tra i runtime selezionabili, perché su Azure Functions Python gira solo su Linux — da qui il flag `--os-type Linux`. Un avviso giallo ti dirà che il piano Linux Consumption verrà ritirato nel 2028: è solo informativo, per un progetto di studio non è un problema.*
15. **Pubblica il codice (deploy).** Il modo più affidabile: `Ctrl+Shift+P` → scrivi `Deploy to Function App` → Invio → scegli il workspace (la cartella del progetto) → scegli la Function App appena creata → conferma l'avviso di sovrascrittura ("This will overwrite any previous deployment" — la prima volta non perdi nulla).
    *Se compare un popup "Initialize project for use with VS Code?", clicca **Yes**: aggiunge solo una cartella `.vscode/` di configurazione per l'estensione, non tocca il tuo codice.*
16. **Testa l'endpoint pubblico.** Stessa richiesta di prima, ma verso l'URL vero invece di `localhost`:
    ```bash
    curl -X POST https://func-supportchatbot-don.azurewebsites.net/api/chat -H "Content-Type: application/json" -d "{\"message\":\"ciao\"}"
    ```
    Oppure con Postman, stessa configurazione ma con l'URL pubblico. Risposta attesa: `{"reply": "hai detto: ciao"}` — stavolta da un server vero su internet, non dal tuo computer.

### Codice

```python
# domain/interfaces.py
from typing import Protocol

class ILLMClient(Protocol):
    def complete(self, prompt: str, context: list[str]) -> str: ...

class IRetriever(Protocol):
    def retrieve(self, query: str) -> list[str]: ...
```

```python
# services/chat_service.py
from domain.interfaces import ILLMClient, IRetriever

class ChatService:
    def __init__(self, retriever: IRetriever, llm: ILLMClient):
        self._retriever = retriever
        self._llm = llm

    def handle(self, message: str) -> str:
        context = self._retriever.retrieve(message)
        return self._llm.complete(message, context)
```

```python
# function_app.py — versione completa di questa fase
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
```

### Cosa costruisci in questa fase

**`domain/interfaces.py`** non contiene logica, solo due contratti: `ILLMClient` dice "qualcosa che sa rispondere a un prompt dato un contesto", `IRetriever` dice "qualcosa che sa recuperare contesto data una query". Nessuno dei due sa *come* farlo — è deliberato.

**`services/chat_service.py`** è la logica di dominio vera. `ChatService` non sa se il suo `llm` è Azure OpenAI, un finto eco, o domani qualcos'altro: conosce solo l'interfaccia. È la **Dependency Inversion** applicata concretamente, non solo citata.

**`function_app.py`** fa tre cose distinte: definisce due implementazioni finte delle interfacce (`EchoLLMClient`, `EmptyRetriever`), costruisce `chat_service` iniettandole, ed espone la funzione `chat` col decoratore `@app.route` — quel decoratore è il **trigger**. La function stessa fa solo da **adapter**, zero logica di business: è il **Single Responsibility Principle**, visibile nel codice invece che solo enunciato. In Fase 2 basterà cambiare **una riga** (`llm=EchoLLMClient()` → `llm=AzureOpenAIClient(...)`) senza toccare il resto.

### Cosa succede, passo dopo passo, quando arriva una richiesta

1. Il runtime di Azure Functions riceve la richiesta HTTP su `/api/chat` → il trigger (`@app.route`) si attiva → chiama `chat(req)`.
2. `chat()` legge il body JSON ed estrae `message`.
3. Chiama `chat_service.handle(message)`.
4. `ChatService.handle()` chiama prima `self._retriever.retrieve(message)` — oggi è `EmptyRetriever`, ritorna sempre `[]`.
5. Poi chiama `self._llm.complete(message, context)` — oggi è `EchoLLMClient`, ritorna `"hai detto: {message}"`.
6. `chat()` impacchetta la risposta in JSON e la restituisce con status `200`.

### Problemi comuni

| Errore | Causa | Soluzione |
|---|---|---|
| "Failed to read app settings file... Error reading JObject" | `local.settings.json` creato vuoto da `func init` | Scrivilo a mano col contenuto mostrato sopra, prima di lanciare `func start` |
| "No job functions found" | `func start` lanciato in una sottocartella (es. `src/`) invece che nella root del progetto | Vai nella cartella che contiene `host.json` prima di lanciare il comando |
| "Unable to access AzureWebJobsStorage" | Azurite non è in esecuzione | Aprilo in un secondo terminale con `azurite` e lascialo acceso |
| Windows: curl restituisce errore di sintassi sul JSON | Le virgolette doppie non sono "escapate" | Usa `-d "{\"message\":\"ciao\"}"` (con i backslash) invece delle virgolette singole di macOS/Linux |
| "Free trial subscription is not supported for Flex Consumption" | La subscription è una Free Trial, che non supporta il piano Flex Consumption proposto di default dal wizard | Crea la Function App via Azure CLI sul piano classico Consumption (vedi comandi sopra) — è supportato anche su Free Trial |
| Python assente dall'elenco runtime nel portale | La tile "Consumption (Windows)" non supporta Python — serve Linux | Usa Azure CLI con `--os-type Linux`, oppure lascia fare al wizard di VS Code che sceglie Linux in automatico |
| "getaddrinfo EAI_AGAIN ...azurewebsites.net" durante il deploy | Il nome DNS della Function App appena creata non si è ancora propagato | Aspetta 2-3 minuti dopo la creazione e riprova il deploy |
| Il tasto destro sulla cartella in Explorer apre un menu sbagliato (Hide Folders, Outline...) | Il click è caduto sull'intestazione del pannello invece che sul nome della cartella | Usa `Ctrl+Shift+P` → `Deploy to Function App` invece del tasto destro — stesso risultato, meno ambiguità |

> **Checkpoint**
> Se domani dovessi sostituire Azure OpenAI con un altro provider LLM, quante righe di `chat_service.py` dovresti toccare? (risposta attesa: zero)
