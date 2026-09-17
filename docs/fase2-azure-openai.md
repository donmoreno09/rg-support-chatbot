# Fase 2 — Collegare Azure OpenAI

Obiettivo: sostituire `EchoLLMClient` con una chiamata reale a un modello Azure OpenAI, autenticata con **Managed Identity** (nessuna API key nel codice).

> Nota: questa versione è adattata rispetto alla guida originale (`progetto-support-chatbot-guida.html`), perché durante l'esecuzione abbiamo incontrato alcuni problemi reali (quota, region, modello deprecato) risolti diversamente da come descritto lì. Questo file è la traccia di cosa è stato **effettivamente fatto**, con la spiegazione di ogni comando e ogni riga di codice.

---

## Checklist

- [x] Risorsa Azure OpenAI creata
- [x] Modello deployato
- [x] Managed Identity attivata sulla Function App
- [x] Ruolo IAM assegnato alla Managed Identity (e all'utente per test locali)
- [x] Pacchetti Python installati
- [x] `infrastructure/azure_openai_client.py` creato
- [x] `function_app.py` aggiornato
- [x] Testato in locale
- [x] Ridistribuito e testato su Azure

**Fase 2 completata.**

---

## Step 1 — Crea la risorsa Azure OpenAI

Nel portale Azure: "Create a resource" → cerca "Azure OpenAI" → Create.

- **Resource group**: `rg-support-chatbot-dev` (quello di Fase 0) — tutte le risorse del progetto restano raggruppate insieme, così puoi vedere/cancellare tutto insieme se serve.
- **Region**: **Sweden Central** — non East US: vedi la riga sulla quota nella tabella dei problemi più sotto, è il motivo per cui abbiamo cambiato region.
- **Name**: `oai-support-chatbot` — diventa parte dell'endpoint pubblico (`https://oai-support-chatbot.openai.azure.com/`), per questo deve essere univoco su tutto Azure.
- **Pricing tier**: Standard S0 — l'unico tier disponibile per Azure OpenAI, paghi solo per i token usati (pay-per-use), non un canone fisso.
- **Network**: "All networks, including the internet, can access this resource" — la Function App gira su piano Consumption, senza VNet integration, quindi comunica per forza sulla rete pubblica. La sicurezza vera qui non la fa il livello di rete: la fa Microsoft Entra ID via Managed Identity + ruolo IAM (Step 4). Anche con la rete aperta a tutti, nessuno può chiamare il modello senza quel ruolo assegnato.

## Step 2 — Deploya il modello

Dalla risorsa → "Go to Azure AI Foundry portal" (se propone la nuova interfaccia "New Foundry" e blocca su una region/risorsa diversa, usa **"Open in Foundry Classic"** — vedi tabella problemi) → **Deployments → Deploy model → Deploy base model**.

- **Modello**: `gpt-4.1-mini` — non `gpt-4o-mini` come nella guida originale, perché quest'ultimo è stato ritirato da Azure il 31/03/2026 (vedi tabella). `gpt-4.1-mini` è il sostituto diretto: stessa Chat Completions API, nessun parametro di reasoning da gestire, costo comunque basso — adatto a un progetto di test.
- **Deployment name**: `chat-deploy` — questo è il nome con cui il codice Python chiamerà il modello (`deployment="chat-deploy"`). Deve combaciare *esattamente*, altrimenti l'errore è `DeploymentNotFound`. Il campo si resetta ogni volta che cambi modello nel wizard, va sempre ricontrollato prima di confermare.
- **Deployment type**: **Standard**, non "Global Standard" — con "Global Standard" la capacity restava bloccata a 0 TPM per via della quota Free Trial; "Standard" (legato direttamente alla risorsa scelta invece che a un pool globale) ha sbloccato una capacity reale.
- **Capacity**: deve mostrare un valore diverso da zero (es. 100K TPM) prima di confermare — a 0 TPM il deployment si crea ma non risponde mai alle chiamate.
- **AI resource**: deve mostrare `oai-support-chatbot` **senza** la dicitura "(create)" — quella dicitura significa che il wizard sta per creare una risorsa nuova e diversa altrove, invece di usare quella che hai già.

## Step 3 — Attiva la Managed Identity sulla Function App

Sulla Function App (`func-supportchatbot-don`) → menu **Identity** (nascosto dentro "Settings" nel menu laterale, se non compare in cima) → tab **System assigned** → **On** → **Save** → conferma nel popup.

Cosa fa: crea un'identità Microsoft Entra ID "posseduta" dalla Function App stessa, senza che tu debba gestire password o chiavi. È il meccanismo con cui, una volta deployata su Azure, la Function potrà autenticarsi verso Azure OpenAI senza avere nessun segreto scritto nel codice o nella configurazione.

## Step 4 — Assegna il ruolo IAM

Sulla risorsa Azure OpenAI → **Access control (IAM)** → **+ Add → Add role assignment** → ruolo **"Cognitive Services OpenAI User"** → **Next**.

Questo ruolo serve a due soggetti diversi, aggiunti nella **stessa schermata "Members"**, uno dopo l'altro (il portale accetta entrambe le selezioni nella stessa operazione — non serve rifare il wizard due volte):

1. **La Function App** (per quando gira su Azure): seleziona **"Managed identity"** → **+ Select members** → tab "System-assigned managed identity" → **Function App** → scegli `func-supportchatbot-don` → Select.
2. **Il tuo utente personale** (per i test in locale): senza uscire da questa schermata, seleziona **"User, group, or service principal"** → **+ Select members** → cerca il tuo indirizzo email → selezionalo → Select.

Perché serve anche il tuo utente: in locale, quando lanci `func start`, la libreria `DefaultAzureCredential` non ha accesso alla Managed Identity (che esiste solo quando il codice gira davvero su Azure) — usa invece la tua identità personale, quella con cui hai fatto `az login`. Senza questa seconda assegnazione, l'endpoint in locale risponderebbe 401 Unauthorized anche con il codice corretto.

Verifica finale prima di confermare: nella tabella sotto "Members" devi vedere **due righe** — `func-supportchatbot-don` (Type: Function App) e il tuo nome (Type: User). Solo a quel punto clicca **Review + assign**.

## Step 5 — Installa i pacchetti Python

Prima, attiva il venv del progetto (se non è già attivo — controlla che il prompt mostri `(.venv)` davanti al percorso):

```bash
.venv\Scripts\activate
```
Questo comando modifica temporaneamente il `PATH` della sessione del terminale, così `pip` e `python` puntano agli eseguibili dentro `.venv/` invece che a quelli installati globalmente sul sistema. Ogni pacchetto installato dopo questo comando finisce isolato in quella cartella, non nell'installazione Python di sistema.

```bash
pip install openai azure-identity
```
Scarica e installa due librerie: `openai` (il client ufficiale per chiamare le API di OpenAI/Azure OpenAI — è quello che useremo per `AzureOpenAI(...)` e `chat.completions.create(...)`) e `azure-identity` (fornisce `DefaultAzureCredential`, il meccanismo che ottiene automaticamente un token da Microsoft Entra ID usando l'identità disponibile — Managed Identity su Azure, la tua utenza `az login` in locale).

```bash
pip freeze > requirements.txt
```
`pip freeze` stampa l'elenco di tutti i pacchetti visibili nell'ambiente Python attivo in quel momento, con le versioni esatte installate. Il simbolo `>` redirige quell'elenco dentro `requirements.txt`, sovrascrivendo il contenuto precedente. Questo file è quello che Azure legge al momento del deploy per sapere quali pacchetti installare sul server remoto — per questo il comando **deve** essere eseguito dentro il venv: se lanciato fuori, elencherebbe anche pacchetti globali del sistema, estranei al progetto, che Azure proverebbe inutilmente a installare (o installerebbe in una versione diversa da quella testata in locale).

## Step 6 — Crea `infrastructure/azure_openai_client.py`

Nuova cartella allo stesso livello di `domain/` e `services/`, con un `__init__.py` vuoto dentro (dice a Python che quella cartella è un package importabile).

```python
# infrastructure/azure_openai_client.py
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI
from domain.interfaces import ILLMClient


class AzureOpenAIClient(ILLMClient):
    def __init__(self, endpoint: str, deployment: str):
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default"
        )
        self._client = AzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version="2024-10-21",
        )
        self._deployment = deployment

    def complete(self, prompt: str, context: list[str]) -> str:
        system = "Rispondi solo usando il contesto fornito. Se non basta, dillo esplicitamente."
        messages = [
            {"role": "system", "content": f"{system}\n\nContesto:\n{chr(10).join(context)}"},
            {"role": "user", "content": prompt},
        ]
        result = self._client.chat.completions.create(model=self._deployment, messages=messages)
        return result.choices[0].message.content
```

Spiegazione riga per riga:

- `from azure.identity import DefaultAzureCredential, get_bearer_token_provider` — importa gli strumenti per l'autenticazione senza chiavi: `DefaultAzureCredential` trova automaticamente quale identità usare (Managed Identity su Azure, il tuo utente `az login` in locale), `get_bearer_token_provider` la trasforma in una funzione che produce token validi su richiesta.
- `from openai import AzureOpenAI` — il client ufficiale della libreria `openai`, nella variante pensata specificamente per Azure (gestisce l'URL e i parametri diversi rispetto a OpenAI diretto).
- `from domain.interfaces import ILLMClient` — l'interfaccia (Protocol) definita in Fase 1. Importarla qui è quello che rende possibile la Dependency Inversion: questa classe concreta dipende dall'astrazione del dominio, non il contrario.
- `class AzureOpenAIClient(ILLMClient):` — dichiara che questa classe implementa il contratto `ILLMClient`: deve avere un metodo `complete(prompt, context) -> str`, esattamente come `EchoLLMClient` in Fase 1.
- `def __init__(self, endpoint: str, deployment: str):` — il costruttore riceve dall'esterno l'URL della risorsa Azure OpenAI e il nome del deployment: la classe non ha nessuna configurazione "cablata" dentro, la riceve da chi la istanzia (in `function_app.py`).
- `token_provider = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")` — crea una funzione che, ogni volta che viene chiamata, chiede a Microsoft Entra ID un token di accesso valido specificamente per i servizi Cognitive Services (che includono Azure OpenAI). Il secondo argomento è lo "scope": dice esplicitamente per quale servizio vogliamo il permesso.
- `self._client = AzureOpenAI(...)` — istanzia il client vero e proprio, passandogli l'endpoint (dove si trova la risorsa), il modo per ottenere i token (`azure_ad_token_provider`, che userà `token_provider` automaticamente prima di ogni chiamata) e la versione dell'API da usare (`api_version`, fissata per evitare che un aggiornamento silenzioso lato Azure cambi comportamento senza preavviso).
- `self._deployment = deployment` — salva il nome del deployment come attributo, servirà in `complete()` per dire al client *quale* modello interrogare.
- `def complete(self, prompt: str, context: list[str]) -> str:` — implementazione del metodo richiesto da `ILLMClient`. Stessa firma di `EchoLLMClient.complete()`: questo è ciò che permette a `ChatService` di usare l'una o l'altra implementazione senza saperne la differenza.
- `system = "..."` — un'istruzione data al modello prima della domanda dell'utente, che gli dice come comportarsi (in questo caso: non inventare risposte oltre al contesto fornito). Con `EmptyRetriever` il contesto è sempre vuoto, quindi in questa fase il modello dirà quasi sempre "non ho contesto sufficiente" — comportamento corretto, non un bug (il contesto vero arriva in Fase 3).
- `messages = [...]` — costruisce la lista di messaggi nel formato richiesto dalla Chat Completions API: un messaggio di ruolo `system` (le istruzioni) seguito da un messaggio di ruolo `user` (la domanda). `chr(10).join(context)` unisce gli elementi della lista `context` con un a-capo (`chr(10)` è il carattere newline) tra uno e l'altro.
- `result = self._client.chat.completions.create(model=self._deployment, messages=messages)` — la chiamata HTTP vera e propria verso Azure OpenAI. `model` qui, nonostante il nome, è il *nome del deployment* (`chat-deploy`), non il nome del modello base (`gpt-4.1-mini`) — è così che Azure OpenAI instrada la richiesta al deployment giusto.
- `return result.choices[0].message.content` — la risposta arriva in una struttura con una lista di possibili completamenti (`choices`); prendiamo il primo (l'unico, di default) ed estraiamo il testo generato.

## Step 7 — Collega tutto in `function_app.py`

Aggiungi l'import in cima al file:
```python
from infrastructure.azure_openai_client import AzureOpenAIClient
```

Poi cambia una riga sola, dove viene istanziato `ChatService`:
```python
llm=AzureOpenAIClient(
    endpoint="https://oai-support-chatbot.openai.azure.com/",
    deployment="chat-deploy"
)
```
al posto di `llm=EchoLLMClient()`.

`IRetriever` resta `EmptyRetriever` per ora — il retrieval vero (Azure AI Search) arriva in Fase 3, e finché resta così il modello continuerà a rispondere "non ho contesto sufficiente" a domande specifiche, com'è giusto che sia.

Pulizia opportuna: la classe `EchoLLMClient` scritta in Fase 1 non è più usata da nessuno — va cancellata del tutto (non solo l'istanza, la definizione della classe), per non lasciare nel file codice morto che nessuno referenzia più.

## Step 8 — Testa in locale, poi ridistribuisci

**Attiva il venv, poi:**
```bash
func start
```
Avvia il runtime di Azure Functions in locale, che legge `function_app.py` e mette in ascolto l'endpoint su `http://localhost:7071/api/chat`. Va eseguito con il venv attivo (`(.venv)` visibile nel prompt) — altrimenti il runtime cerca i pacchetti nell'installazione Python globale del sistema invece che in quella del venv dove sono stati installati, causando `ModuleNotFoundError`.

**Test con Postman** (alternativa a `curl.exe`, utile perché in PowerShell l'alias `curl` punta a `Invoke-WebRequest`, che ha una sintassi diversa e non accetta `-H`/`-d` come il curl vero):
- Metodo: `POST`
- URL: `http://localhost:7071/api/chat`
- Body → raw → JSON: `{"message": "ciao"}`

Risposta attesa (con `EmptyRetriever`, quindi contesto vuoto): qualcosa come *"Non hai fornito contesto sufficiente..."* — è la prova che il modello sta rispondendo davvero, seguendo il system prompt, non più l'eco di Fase 1.

**Ridistribuisci:**
In VS Code, `Ctrl+Shift+P` → **"Deploy to Function App"** → seleziona `func-supportchatbot-don` → conferma la sovrascrittura. Stesso meccanismo di Fase 1: pacchetta il codice e lo carica sulla Function App remota, che a quel punto reinstalla le dipendenze leggendo `requirements.txt`.

**Test sull'endpoint pubblico**, stessa configurazione di Postman ma con l'URL:
```
https://func-supportchatbot-don.azurewebsites.net/api/chat
```

Risposta identica (o comunque coerente) a quella locale conferma che tutta la catena funziona: Function App → Managed Identity → Azure OpenAI, senza nessuna chiave in chiaro da nessuna parte.

---

## Problemi incontrati e soluzioni

| Errore | Causa | Soluzione |
|---|---|---|
| Network Type nel wizard di creazione risorsa | Scelta non spiegata dalla guida originale | "All networks" — la sicurezza è su IAM/Managed Identity, non sulla rete |
| Deploy model propone di creare una **nuova** risorsa AI in un'altra region, campo non modificabile | La nuova interfaccia "New Foundry" rileva che il tipo di deployment scelto non ha capacità nella region della risorsa esistente | Passa a "Open in Foundry Classic", oppure cambia region della risorsa AI |
| `InsufficientQuota` — "Cannot create/update/move resource" durante la creazione della risorsa | Una risorsa con lo stesso tipo era stata cancellata ma non purgata: resta in soft-delete e continua a occupare la quota della subscription (Free Trial) | `az cognitiveservices account list-deleted` per trovarla, poi `az cognitiveservices account purge --name <nome> --resource-group <rg> --location <region>` |
| Capacity bloccata a **0 tokens per minute (TPM)**, non modificabile, sia con "Global Standard" che "Standard" in East US / East US 2 | Le subscription **Free Trial** partono con quota 0 TPM di default per i modelli interattivi in molte region | Provare altre region (Sweden Central ha sbloccato la capacity con deployment type "Standard"); in alternativa fare upgrade a Pay-As-You-Go (il credito residuo della Free Trial viene comunque consumato per primo) |
| `ServiceModelDeprecated` — "The model ... gpt-4o-mini ... has been deprecated since 03/31/2026" | `gpt-4o-mini` è stato ritirato da Azure OpenAI | Usato `gpt-4.1-mini` come sostituto diretto — stessa Chat Completions API, nessun parametro di reasoning richiesto |
| `func start` fallisce con `ModuleNotFoundError: No module named 'azure.identity'`, anche se il pacchetto risultava installato | `func start` era lanciato da un cmd normale, nella cartella giusta del progetto ma **senza il venv attivo** — il prompt non mostrava `(.venv)` davanti al percorso. Il runtime quindi cercava i moduli nell'installazione Python globale, non in quella del venv dove `pip install` li aveva messi | Attivare il venv (`.venv\Scripts\activate`, verificare che compaia `(.venv)` nel prompt) **prima** di lanciare `func start` — la sola cartella corretta non basta, serve anche l'ambiente virtuale attivo |
| Risorsa cancellata: il nome non è subito riutilizzabile | Soft-delete: Azure riserva il nome per un periodo (in genere fino a 48h, o finché non viene purgato) | Usare un nome leggermente diverso, oppure purgare la risorsa cancellata (vedi sopra) |
| `curl` in PowerShell dà errore `Cannot bind parameter 'Headers'` con `-H`/`-d` | In PowerShell `curl` è un alias di `Invoke-WebRequest`, con sintassi diversa dal curl reale | Usare `curl.exe` esplicitamente per bypassare l'alias, oppure testare da Postman |

---

## Riepilogo di cosa è stato fatto in questa fase

In Fase 1 l'endpoint `/api/chat` rispondeva con un eco finto (`EchoLLMClient`). In questa fase quell'implementazione è stata sostituita con una vera, senza toccare nessun'altra parte del progetto — `ChatService` e l'interfaccia `ILLMClient` sono rimasti identici, a dimostrazione pratica che l'architettura a layer scelta in Fase 1 (domain → services → infrastructure) regge il cambiamento.

Concretamente:

1. **Infrastruttura Azure creata**: una risorsa Azure OpenAI (`oai-support-chatbot`, region Sweden Central, dopo aver escluso East US per problemi di quota) con un deployment del modello `gpt-4.1-mini` (nome deployment `chat-deploy`, tipo Standard, capacity 100K TPM).
2. **Autenticazione senza segreti**: Managed Identity attivata sulla Function App, con il ruolo "Cognitive Services OpenAI User" assegnato sia alla Managed Identity (per la produzione su Azure) sia al proprio utente personale (per i test in locale, dove `DefaultAzureCredential` usa l'identità di `az login`).
3. **Nuovo layer infrastructure**: creata la cartella `infrastructure/` con `azure_openai_client.py`, contenente `AzureOpenAIClient`, un adapter che implementa `ILLMClient` chiamando davvero Azure OpenAI tramite la libreria `openai`, autenticandosi con un token Entra ID ottenuto automaticamente (mai una API key scritta nel codice).
4. **Collegamento**: in `function_app.py`, una sola riga cambiata per iniettare `AzureOpenAIClient` al posto di `EchoLLMClient` — `EmptyRetriever` resta invariato, il contesto rimane vuoto fino alla Fase 3.
5. **Verifica end-to-end**: testato sia in locale (`func start` + Postman) sia sull'endpoint pubblico dopo il redeploy, confermando che l'intera catena Function App → Managed Identity → Azure OpenAI funziona.

Punto chiave per il colloquio: l'autenticazione è interamente basata su Managed Identity e ruoli IAM (RBAC), mai su chiavi API in chiaro — ed è un cambiamento che ha richiesto di toccare *una riga* di codice applicativo, perché tutto il resto dipendeva solo da un'astrazione (`ILLMClient`), non da un'implementazione concreta.
