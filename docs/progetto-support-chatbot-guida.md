# Assistente di Supporto Tecnico RAG — Guida completa passo passo

> **Colloquio Azure AI Conversational · Progetto pratico**
> Un chatbot di supporto che legge documentazione interna, risponde usando Azure OpenAI con la tecnica RAG (per non "inventare" risposte), e sa passare la palla a un umano quando non trova nulla di utile.

Questa guida è pensata per chi parte da zero su Azure. Ogni fase spiega: **cosa fare** (passo dopo passo), **cosa significa** ogni termine tecnico incontrato, **cosa succede davvero** quando il sistema gira, e **quali errori** è più probabile incontrare (con la causa e la soluzione).

---

## 0. Prima di tutto: un glossario dei termini che incontrerai spesso

Non serve leggerlo tutto subito — torna qui ogni volta che un termine non ti è chiaro.

| Termine | Cosa significa |
|---|---|
| **Azure** | La piattaforma cloud di Microsoft: invece di comprare e gestire server fisici, "affitti" risorse (potenza di calcolo, spazio, database...) da Microsoft, pagando solo quello che usi. |
| **Resource Group** | Un contenitore logico dentro Azure. Raggruppa tutte le risorse di un progetto (server, database, ecc.) così puoi vederle, gestirle ed eliminarle tutte insieme, invece che una per una. |
| **Azure Functions** | Un servizio che fa girare piccoli pezzi di codice ("funzioni") solo quando serve — ad esempio quando arriva una richiesta HTTP — senza che tu debba gestire un server acceso 24 ore su 24. Paghi (quasi) solo quando la funzione viene eseguita. |
| **Trigger** | L'evento che "sveglia" ed esegue una Azure Function. Può essere una richiesta HTTP, un nuovo messaggio in una coda, un timer, ecc. |
| **API REST** | Un modo standard di far comunicare due programmi via HTTP: un client manda una richiesta (es. "dammi la risposta a questo messaggio") a un URL, e il server risponde con dei dati (di solito in formato JSON). |
| **RAG (Retrieval-Augmented Generation)** | Una tecnica per far rispondere un modello di AI in modo più affidabile: prima **recuperi** (retrieval) i documenti più pertinenti da una base di conoscenza, poi li dai al modello come "contesto" insieme alla domanda, così il modello risponde basandosi su quei documenti invece di inventare. |
| **Grounding** | L'effetto pratico del RAG: la risposta del modello è "ancorata" a fatti reali (i documenti recuperati), non è un'invenzione plausibile ma falsa (chiamata **allucinazione**). |
| **Key Vault** | Una "cassaforte" digitale di Azure per salvare segreti (password, chiavi API, certificati) in modo sicuro e centralizzato, invece di scriverli in chiaro dentro il codice o nei file di configurazione. |
| **Managed Identity** | Un'identità che Azure assegna automaticamente a una risorsa (es. la tua Function App), che quella risorsa può usare per autenticarsi verso altri servizi Azure **senza bisogno di password o chiavi salvate da qualche parte**. È il modo "giusto" e sicuro di far comunicare due servizi Azure tra loro. |
| **RBAC (Role-Based Access Control)** | Il sistema con cui Azure decide "chi può fare cosa": assegni un **ruolo** (es. "Contributor", "Cognitive Services OpenAI User") a un utente o a una Managed Identity su una risorsa specifica, e quel ruolo definisce i permessi. |
| **IAM (Identity and Access Management)** | Il pannello dentro ogni risorsa Azure dove assegni i ruoli RBAC — lo trovi cercando "Access control (IAM)". |
| **venv (virtual environment)** | Una "bolla" isolata dove installare le librerie Python solo per un progetto specifico, così non si mescolano con quelle di altri progetti sul tuo computer. |
| **Subscription Free Trial** | Il tipo di sottoscrizione Azure che Microsoft dà gratuitamente ai nuovi account (con un credito iniziale). Ha alcune limitazioni rispetto a una subscription "pay-as-you-go" a pagamento — ad esempio, come vedrai in Fase 1, non supporta il piano di hosting "Flex Consumption". |
| **Piano di hosting (Consumption / Flex Consumption)** | Il "contratto" che decide come viene fatturata ed eseguita una Function App. **Consumption** (il piano classico) paga solo l'esecuzione effettiva e scala automaticamente. **Flex Consumption** è una versione più recente con opzioni aggiuntive (es. più controllo sulla scalabilità), ma non è disponibile su tutte le subscription — in particolare non sulle Free Trial. |
| **Azure CLI** | Uno strumento a riga di comando (il comando è `az`) per creare e gestire risorse Azure scrivendo comandi invece di cliccare nel portale — utile quando il wizard grafico non offre l'opzione che ti serve. |
| **Command Palette (Ctrl+Shift+P)** | Il "menu dei comandi" di VS Code: premendo `Ctrl+Shift+P` (o `Cmd+Shift+P` su Mac) si apre una barra di ricerca dove puoi digitare il nome di un'azione (es. "Deploy to Function App") ed eseguirla, senza dover cercare il pulsante giusto nell'interfaccia. |
| **Propagazione DNS** | Il tempo che serve perché un nuovo indirizzo internet (es. il nome della tua Function App appena creata) diventi raggiungibile da tutti i computer del mondo — di solito pochi minuti, ma non è mai istantaneo. |
| **Azurite** | Un programma che simula sul tuo computer i servizi di storage di Azure (code, file, tabelle), così puoi sviluppare e testare le Function **in locale**, senza dover usare (e pagare) uno storage account Azure vero. |
| **CORS (Cross-Origin Resource Sharing)** | Una regola di sicurezza che i browser applicano di default: un sito web non può chiamare un indirizzo diverso dal proprio a meno che quell'indirizzo non lo permetta esplicitamente. Se il tuo widget e la tua Function stanno su domini diversi, devi "autorizzare" il dominio del widget lato Function. |
| **Application Insights** | Il servizio Azure che raccoglie automaticamente log, errori e metriche di prestazione della tua applicazione, e te li rende interrogabili in un linguaggio chiamato KQL. |
| **KQL (Kusto Query Language)** | Il linguaggio di interrogazione usato per cercare dentro i log di Application Insights (e di altri servizi Azure Monitor) — concettualmente simile a SQL, ma pensato per i log. |
| **PTU (Provisioned Throughput Units)** | Un modello di prezzo di Azure OpenAI in cui **prenoti e paghi** una capacità di calcolo fissa al mese, indipendentemente da quanto la usi. Alternativa al modello "pay-as-you-go" (paghi solo i token che consumi). |
| **Embedding** | Una rappresentazione numerica (un vettore di numeri) del significato di un testo. Testi con significato simile hanno vettori "vicini" tra loro — è quello che permette la ricerca semantica (cercare per significato, non solo per parole esatte). |
| **SOLID / Dependency Inversion** | Un insieme di principi di buona progettazione del software. Il pezzo che useremo di più qui è la **Dependency Inversion**: il codice che orchestra la logica (es. `ChatService`) dipende da un'**interfaccia astratta** (un contratto), non da un'implementazione concreta specifica. Questo permette di cambiare l'implementazione (es. passare da un LLM finto a uno vero) modificando una riga sola, senza toccare la logica di business. |

---

## 1. Come è organizzata questa guida

Il progetto è diviso in **9 fasi (0-8)**. Ogni fase segue sempre la stessa struttura:

1. **Come si fa, passo dopo passo** — le azioni concrete da compiere (click nel portale, comandi da terminale, file da scrivere).
2. **Codice completo** — non estratti parziali, così puoi copiare e far girare tutto.
3. **Cosa succede quando arriva una richiesta** — una traccia mentale di cosa fa il sistema, riga per riga, così capisci *perché* funziona (o non funziona) e non solo *come* farlo funzionare.
4. **Problemi comuni** — gli errori più probabili, la loro causa reale, e come risolverli.
5. **Perché per il colloquio** / **Checkpoint** — il collegamento tra quello che hai fatto e cosa potrebbero chiederti in un colloquio.

---

## 2. Copertura dei requisiti

Ogni riga dell'annuncio di lavoro è mappata su una fase concreta del progetto, così a fine percorso avrai toccato con mano ogni competenza richiesta.

| Requisito dall'annuncio | Fase |
|---|---|
| Conoscenza della piattaforma Microsoft Azure | Fase 0 |
| Azure Functions | Fase 1, Fase 5 |
| Application Insights | Fase 4 |
| Azure OpenAI | Fase 2 |
| Python | Trasversale (in tutte le fasi) |
| API REST | Fase 1 |
| Implementazione soluzioni RAG | Fase 3 |
| Gestione sottoscrizioni/consumi (PTU) | Fase 7 |
| Integrazione widget e sistemi enterprise | Fase 6 |
| Nice to have — Copilot Studio | Fase 8 |
| Nice to have — NLU / CLU | Fase 8 |

---

## 3. Architettura d'insieme

Prima di scrivere codice, ecco come i pezzi si parlano tra loro. Ci sono due flussi:

**Flusso principale (sincrono — l'utente aspetta la risposta):**

```
Widget (HTML/JS)
      │  richiesta HTTP con il messaggio dell'utente
      ▼
API Function (/api/chat)          ← Fase 1
      │  chiama
      ▼
Chat Service                       ← orchestra tutto, non sa nulla di Azure
      │                             (dipende solo da interfacce astratte)
      ├──► Azure AI Search  (recupera i documenti pertinenti)   ← Fase 3
      └──► Azure OpenAI     (genera la risposta usando quei documenti) ← Fase 2
      │
      ▼
Cosmos DB (salva lo stato della conversazione)
```

**Flusso di escalation (asincrono — parte in background):**

```
Chat Service → Queue Function (Fase 5) → Ticket System / sistema enterprise (Fase 6)
```

**Osservabilità (trasversale, non blocca nulla):**
Application Insights (Fase 4) osserva ogni passaggio del flusso principale e registra tempi, errori e metriche, senza rallentare la risposta all'utente.

Il punto chiave dell'architettura: **`function_app.py` fa solo da traduttore HTTP ↔ Python** (si chiama "adapter"), mentre tutta la logica vive in `ChatService`, che a sua volta non sa *mai* se sta parlando con Azure OpenAI vero o con una versione finta — conosce solo un'interfaccia. Questo è il principio di **Dependency Inversion** (parte dei principi SOLID): il livello "alto" (la logica di business) non dipende da dettagli "bassi" (quale servizio cloud usi), ma da un'astrazione condivisa. Vantaggio pratico: in Fase 2 basterà cambiare **una riga** di codice per passare da un LLM finto a uno vero, senza toccare `ChatService`.

---

## 4. Prerequisiti — strumenti da installare (una volta sola)

Se hai già installato qualcosa di questo elenco, salta pure quel punto.

1. **Python 3.11.** Scaricalo da `python.org/downloads`. Su Windows, durante l'installazione spunta l'opzione "Add Python to PATH" (altrimenti il terminale non troverà il comando `python`). Verifica che sia installato:
   ```bash
   python --version
   ```

2. **Visual Studio Code (VS Code).** L'editor di codice che useremo, da `code.visualstudio.com`. È gratuito.

3. **Estensione "Azure Functions" per VS Code.** Apri il pannello Extensions (l'icona a quadrati nella barra laterale sinistra), cerca "Azure Functions", clicca Install. Aggiunge un pannello dedicato per creare, testare e pubblicare le Function direttamente da VS Code.

4. **Node.js** (versione LTS, da `nodejs.org`). Serve solo perché il prossimo strumento si installa tramite `npm` (il gestore di pacchetti di Node.js).

5. **Azure Functions Core Tools.** È il programma che fa girare le Azure Functions **sul tuo computer**, in locale, prima di pubblicarle davvero su Azure — così puoi testare senza pubblicare ogni volta.
   ```bash
   npm install -g azure-functions-core-tools@4 --unsafe-perm true
   ```
   `npm install -g` significa "installa questo pacchetto globalmente sul computer", non solo in un progetto.

6. **Azure CLI.** Un programma da riga di comando per gestire le risorse Azure senza passare dal portale web. Dopo averlo installato, autenticati con:
   ```bash
   az login
   ```
   Questo apre il browser, ti fa fare login col tuo account Azure, e da quel momento il terminale "sa chi sei" per i comandi successivi.

7. **Azurite.** Come spiegato nel glossario, simula lo storage di Azure sul tuo computer.
   ```bash
   npm install -g azurite
   ```

8. **Un account Azure attivo**, con una subscription pay-as-you-go oppure i crediti gratuiti che Microsoft offre ai nuovi account (`azure.microsoft.com/free`).

9. **Postman** (opzionale, da `postman.com/downloads`). Un programma con interfaccia grafica per testare le API REST senza scrivere comandi `curl` a mano — utile se preferisci una GUI.

> **Nota sulla sicurezza:** `local.settings.json` (lo creerai in Fase 1) conterrà i tuoi segreti *in locale* — va sempre inserito nel `.gitignore` e non va mai caricato su Git. Su Azure vero, invece, non useremo mai API key scritte in chiaro: useremo la Managed Identity spiegata nel glossario.

---

## FASE 0 — Fondamenta Azure

**Cosa costruiamo:** il "terreno" su cui appoggeremo tutto il resto: un contenitore per le risorse, una cassaforte per i segreti, e un allarme che ti avvisa se stai spendendo troppo.

### Come si fa, passo dopo passo

1. **Crea il Resource Group.**
   Vai su `portal.azure.com` e fai login. Nella barra di ricerca in alto scrivi "Resource groups" → **+ Create**. Scegli la tua subscription, dai il nome `rg-support-chatbot-dev`, region "West Europe" → **Review + create** → **Create**.
   *Perché:* come spiegato nel glossario, un Resource Group è solo un contenitore logico — ti permette di vedere, gestire ed eliminare **tutte** le risorse del progetto in un colpo solo, invece di cercarle una per una.

2. **Crea il Key Vault.**
   Cerca "Key Vault" → **+ Create**. Usa il Resource Group appena creato, dai un nome univoco **su tutto Azure** (es. `kv-supportchatbot-don`), stessa region, pricing tier "Standard" → **Review + create** → **Create**.
   *Perché:* è la cassaforte dove in futuro potresti salvare segreti che non vuoi in chiaro nel codice. In questo progetto useremo soprattutto Managed Identity (quindi meno segreti da gestire a mano), ma è comunque uno strumento fondamentale da conoscere e avere pronto.

3. **Imposta un budget di sicurezza.**
   Cerca "Cost Management + Billing" → **Budgets** → **+ Add**. Scope: la subscription. Importo, ad esempio 20€/mese. Imposta un avviso email all'80% e al 100% della soglia → Salva.
   *Perché:* è un allarme automatico via email se stai per superare la spesa che ti sei fissato — utile perché con risorse cloud è facile dimenticarsi qualcosa acceso e ricevere una bolletta sorpresa.

### Problemi comuni

| Errore | Causa | Soluzione |
|---|---|---|
| "Name not available" | Il nome del Key Vault deve essere univoco su **tutto** Azure, non solo nel tuo account | Aggiungi un suffisso personale o numerico al nome |
| "You do not have permissions..." | Il tuo utente non ha un ruolo sufficiente sulla subscription | Serve almeno il ruolo Contributor — chiedi a chi gestisce la subscription se non lo hai |

- [ ] Resource Group creato
- [ ] Key Vault creato
- [ ] Budget alert attivo

> **🎯 Perché per il colloquio:** organizzare le risorse in modo governabile — non solo farle "funzionare" — è esattamente ciò che serve nel troubleshooting quotidiano su un chatbot già in produzione.

> **Checkpoint:** sapresti spiegare perché il budget alert va impostato *prima* di creare risorse costose, e non dopo?

---

## FASE 1 — Scaffold della Function e endpoint REST

**Cosa costruiamo:** l'endpoint `/api/chat`, strutturato bene fin dall'inizio: la Function fa solo da "traduttore" HTTP, tutta la logica vive in `ChatService`, che dipende da astrazioni e non da Azure direttamente (Dependency Inversion, vedi glossario).

### Come si fa, passo dopo passo

1. **Crea la cartella del progetto e aprila in VS Code.**
   ```bash
   mkdir support-chatbot
   cd support-chatbot
   code .
   ```
   `mkdir` crea la cartella, `cd` ci entra, `code .` apre VS Code puntando alla cartella corrente (`.`).

2. **Apri il terminale integrato.** Menu **Terminal → New Terminal** dentro VS Code, così non devi passare a una finestra separata.

3. **Crea e attiva un ambiente virtuale (venv).**
   ```bash
   python -m venv .venv
   ```
   Questo crea la "bolla" isolata spiegata nel glossario, dentro una cartella nascosta `.venv`. Poi la attivi:
   ```bash
   # macOS / Linux
   source .venv/bin/activate

   # Windows (PowerShell)
   .venv\Scripts\Activate.ps1
   ```
   Se ha funzionato, vedrai `(.venv)` comparire all'inizio della riga del terminale — è la conferma visiva che sei "dentro" l'ambiente isolato.

4. **Inizializza il progetto Function.**
   ```bash
   func init . --python -m V2
   ```
   Questo comando genera automaticamente alcuni file base:
   - `host.json` — configurazione generale del progetto Function.
   - `requirements.txt` — l'elenco delle librerie Python che il progetto usa (come un "carrello della spesa" per `pip`).
   - `.funcignore` — dice quali file **non** includere quando pubblichi su Azure (simile a `.gitignore`, ma per il deploy).
   - `local.settings.json` — le variabili di configurazione/segreti usate solo in locale.

   `-m V2` sceglie il **modello di programmazione v2**, quello moderno basato su decoratori Python (li vedrai tra poco, es. `@app.route`). Il vecchio modello v1 richiedeva una cartella separata per ogni funzione con un file `function.json` a parte — il v2 è più semplice e "pythonico".

5. **Scrivi subito `local.settings.json`.**
   Il file viene creato vuoto (0 byte), e questo causa un avviso finché non lo riempi — conviene farlo subito. Apri il file e sostituisci tutto con:
   ```json
   {
     "IsEncrypted": false,
     "Values": {
       "AzureWebJobsStorage": "UseDevelopmentStorage=true",
       "FUNCTIONS_WORKER_RUNTIME": "python"
     }
   }
   ```
   `AzureWebJobsStorage` dice al runtime **dove** tenere il proprio "libro contabile" interno (trigger, code, timer) — è una necessità tecnica del motore di Azure Functions, non riguarda la tua logica. `UseDevelopmentStorage=true` punta ad Azurite (che avvierai tra poco), così in locale non ti serve uno storage account Azure vero e pagante.

6. **Crea la function collegata a un trigger HTTP.**
   ```bash
   func new
   ```
   Il comando è interattivo, ti farà delle domande:
   - Tipo di trigger → scegli **HTTP trigger**.
   - Nome della funzione → scrivi `chat`.
   - **Auth Level** → tre opzioni:
     - `FUNCTION`: richiede una chiave segreta nell'URL per poter chiamare l'endpoint.
     - `ANONYMOUS`: nessuna chiave, chiunque conosca l'URL può chiamarlo.
     - `ADMIN`: richiede una master key, con privilegi amministrativi.

     Scegli **ANONYMOUS**. Perché: il widget che costruirai in Fase 6 chiamerà l'endpoint direttamente dal browser dell'utente finale — e una function key scritta nel codice JavaScript sarebbe comunque visibile a chiunque apra gli strumenti sviluppatore del browser, quindi non offrirebbe una vera protezione. La sicurezza reale la aggiungeremo altrove (CORS, ed eventualmente un servizio dedicato come API Management).

7. **Crea le cartelle `domain/` e `services/`** nella root del progetto — allo stesso livello di `function_app.py`, **non** dentro una sottocartella tipo `src/`. Dentro ciascuna crea anche un file vuoto `__init__.py`: questo file (vuoto va benissimo) dice a Python "questa cartella è un package importabile", cioè permette di scrivere `from domain.interfaces import ...` da un altro file.

8. **Scrivi `domain/interfaces.py`** col codice mostrato sotto.

9. **Scrivi `services/chat_service.py`** col codice mostrato sotto.

10. **Sostituisci tutto `function_app.py`** (quello generato automaticamente da `func new`, che contiene codice di esempio) con il codice completo mostrato sotto.

11. **Avvia Azurite in un secondo terminale**, lasciandolo acceso in background (non chiuderlo mentre sviluppi — deve restare avviato in parallelo):
    ```bash
    azurite
    ```

12. **Torna al terminale principale**, assicurati di essere nella **root** del progetto (quella che contiene `host.json` — usa `dir` su Windows o `ls` su macOS/Linux per controllare il contenuto della cartella), poi avvia il progetto:
    ```bash
    func start
    ```
    Questo comando avvia un piccolo server web sul tuo computer (di solito su `http://localhost:7071`). Nel terminale vedrai stampato l'URL esatto del tuo endpoint, tipo `http://localhost:7071/api/chat`.

13. **Testa l'endpoint.**
    ```bash
    # macOS / Linux
    curl -X POST http://localhost:7071/api/chat \
      -H "Content-Type: application/json" \
      -d '{"message":"ciao"}'

    # Windows (cmd/PowerShell — le virgolette interne vanno "escapate")
    curl -X POST http://localhost:7071/api/chat -H "Content-Type: application/json" -d "{\"message\":\"ciao\"}"
    ```
    Spiegazione del comando `curl`: `-X POST` dice "manda una richiesta di tipo POST" (cioè "sto inviando dei dati", diverso da GET che è "voglio ricevere dati"); `-H "Content-Type: application/json"` dice al server "il corpo della richiesta che ti sto mandando è in formato JSON"; `-d '...'` è il **d**ata, cioè il contenuto vero e proprio della richiesta.

    In alternativa, con Postman: **New → HTTP Request** → metodo **POST** → incolla l'URL → tab **Body → raw → JSON** → scrivi `{"message": "ciao"}` → **Send**.

14. **Crea la Function App su Azure.**
    Qui la strada da seguire dipende dal tipo di subscription che hai:

    - **Con una subscription pay-as-you-go**, puoi usare il wizard grafico: pannello Azure di VS Code → sotto "Resources" → tasto destro sulla subscription → **Create Function App in Azure (Advanced)**: dai un nome univoco, runtime "Python 3.11", stesso resource group della Fase 0, tipo di hosting "Consumption".

    - **Con una subscription Free Trial** (la più comune per chi inizia), quel wizard — e anche il portale web — propongono di default il piano **Flex Consumption**, che però non è supportato sulle Free Trial: otterresti l'errore `"Free trial subscription is not supported for Flex Consumption"`. In questo caso conviene creare la Function App via **Azure CLI**, specificando esplicitamente il piano classico "Consumption" (quello sì supportato anche su Free Trial):
      ```bash
      # 1. Storage account (nome univoco, solo minuscole/numeri, max 24 caratteri)
      az storage account create --name stsupportchatbotdon --resource-group rg-support-chatbot-dev --location eastus --sku Standard_LRS

      # 2. Function App, piano Consumption classico, Linux, Python
      az functionapp create --resource-group rg-support-chatbot-dev --consumption-plan-location eastus --runtime python --runtime-version 3.11 --functions-version 4 --name func-supportchatbot-don --storage-account stsupportchatbotdon --os-type Linux
      ```
      Spiegazione dei comandi: il primo crea lo **storage account** che la Function App userà per il proprio bookkeeping interno (lo stesso ruolo che in locale era svolto da Azurite, ma stavolta è vero e su Azure). Il secondo crea la Function App vera e propria: `--runtime python --runtime-version 3.11` dice quale linguaggio e versione userà, `--functions-version 4` è la versione del motore Azure Functions, `--consumption-plan-location` sceglie la region per il piano Consumption, e `--os-type Linux` è importante — Azure Functions per Python gira **solo su Linux**: la tile "Consumption (Windows)" del portale infatti non fa mai comparire Python tra i runtime selezionabili. Potresti vedere un avviso giallo che dice che il piano Linux Consumption verrà ritirato nel 2028: è solo informativo, per un progetto di studio non è un problema.

15. **Pubblica il codice (deploy).**
    Il modo più affidabile è usare la **Command Palette** di VS Code: `Ctrl+Shift+P` (o `Cmd+Shift+P` su Mac) → scrivi "Deploy to Function App" → Invio → scegli il workspace (la cartella del progetto) → scegli la Function App appena creata → conferma l'avviso di sovrascrittura ("This will overwrite any previous deployment" — la prima volta non perdi nulla, dato che non c'era ancora nessun deploy precedente).

    Se compare un popup "Initialize project for use with VS Code?", clicca **Yes**: aggiunge solo una cartella `.vscode/` di configurazione per l'estensione, non tocca il tuo codice applicativo.

16. **Testa l'endpoint pubblico.**
    Stessa identica richiesta di prima, ma stavolta verso l'URL vero invece che verso `localhost`:
    ```bash
    curl -X POST https://func-supportchatbot-don.azurewebsites.net/api/chat -H "Content-Type: application/json" -d "{\"message\":\"ciao\"}"
    ```
    Oppure con Postman, stessa configurazione di prima ma con l'URL pubblico al posto di quello locale. Risposta attesa: `{"reply": "hai detto: ciao"}` — stavolta arriva da un server vero su internet, non dal tuo computer.

### Il codice

```python
# domain/interfaces.py
from typing import Protocol

class ILLMClient(Protocol):
    def complete(self, prompt: str, context: list[str]) -> str: ...

class IRetriever(Protocol):
    def retrieve(self, query: str) -> list[str]: ...
```
`Protocol` (da `typing`) è il modo in cui Python esprime un'**interfaccia**: un contratto che dice "qualunque classe abbia questo metodo, con questa firma, va bene" — senza che quella classe debba dichiarare esplicitamente "io implemento questa interfaccia" (si chiama *structural typing*, tipizzazione strutturale). `ILLMClient` dice: "qualunque cosa tu sia, so che sai rispondere a un prompt dato un contesto". `IRetriever` dice: "qualunque cosa tu sia, so che sai recuperare del contesto data una query". Nessuno dei due sa *come* farlo — ed è voluto: è proprio questo che rende possibile sostituire l'implementazione in futuro senza toccare chi la usa.

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
`ChatService` è la logica di dominio vera e propria. Non sa se `self._llm` è Azure OpenAI, un modello finto, o un domani un modello locale: conosce solo l'interfaccia `ILLMClient`. Questo è il principio **Dependency Inversion** (la "D" di SOLID) applicato concretamente: la classe che orchestra dipende da un'**astrazione**, non da un'implementazione concreta — così puoi cambiare l'implementazione senza mai toccare questa classe.

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
`@app.route(...)` è il **decoratore** che collega la funzione Python sottostante al trigger HTTP — dice ad Azure "quando arriva una richiesta HTTP su `/api/chat`, esegui questa funzione". `EchoLLMClient` ed `EmptyRetriever` sono implementazioni **finte** (in gergo si chiamano anche *stub* o *fake*) delle due interfacce, usate solo per verificare che l'impalcatura funzioni prima di collegare i servizi Azure veri.

### Cosa succede, passo dopo passo, quando arriva una richiesta

1. Il runtime di Azure Functions riceve la richiesta HTTP su `/api/chat` → il trigger (`@app.route`) si attiva → chiama `chat(req)`.
2. `chat()` legge il corpo (body) della richiesta in formato JSON ed estrae il campo `message`.
3. Chiama `chat_service.handle(message)`.
4. `ChatService.handle()` chiama prima `self._retriever.retrieve(message)` — oggi è `EmptyRetriever`, quindi ritorna sempre una lista vuota `[]`.
5. Poi chiama `self._llm.complete(message, context)` — oggi è `EchoLLMClient`, quindi ritorna semplicemente `"hai detto: {message}"`.
6. `chat()` impacchetta la risposta in JSON e la restituisce con status HTTP `200` (che significa "richiesta andata a buon fine").

**Nota importante:** `function_app.py` fa solo da **adapter** (traduce HTTP in chiamate Python e viceversa), zero logica di business — tutta la logica sta in `ChatService`. In Fase 2 basterà cambiare **una riga** (`llm=EchoLLMClient()` diventerà `llm=AzureOpenAIClient(...)`) senza toccare nient'altro: è la dependency inversion applicata in pratica, non solo in teoria.

### Problemi comuni

| Errore | Causa | Soluzione |
|---|---|---|
| "Failed to read app settings file... Error reading JObject" | `local.settings.json` creato vuoto da `func init` | Scrivilo a mano col contenuto mostrato sopra, prima di lanciare `func start` |
| "No job functions found" | `func start` lanciato in una sottocartella (es. `src/`) invece che nella root del progetto | Vai nella cartella che contiene `host.json` prima di lanciare il comando |
| "Unable to access AzureWebJobsStorage" | Azurite non è in esecuzione | Aprilo in un secondo terminale con `azurite` e lascialo acceso |
| Windows: curl restituisce errore di sintassi sul JSON | Le virgolette doppie non sono "escapate" | Usa `-d "{\"message\":\"ciao\"}"` (con i backslash) invece delle virgolette singole di macOS/Linux |
| `"Free trial subscription is not supported for Flex Consumption"` | La subscription è una Free Trial, che non supporta il piano Flex Consumption proposto di default dal wizard | Crea la Function App via Azure CLI sul piano classico Consumption (vedi comandi sopra) — è supportato anche su Free Trial |
| Python assente dall'elenco runtime nel portale | La tile "Consumption (Windows)" non supporta Python — serve Linux | Usa Azure CLI con `--os-type Linux`, oppure lascia fare al wizard di VS Code che sceglie Linux in automatico |
| `"getaddrinfo EAI_AGAIN ...azurewebsites.net"` durante il deploy | Il nome DNS della Function App appena creata non si è ancora propagato (vedi glossario) | Aspetta 2-3 minuti dopo la creazione e riprova il deploy |
| Il tasto destro sulla cartella in Explorer apre un menu sbagliato (Hide Folders, Outline...) | Il click è caduto sull'intestazione del pannello invece che sul nome della cartella | Usa `Ctrl+Shift+P` → "Deploy to Function App" invece del tasto destro — stesso risultato, meno ambiguità |

> **Checkpoint:** se domani dovessi sostituire Azure OpenAI con un altro provider LLM, quante righe di `chat_service.py` dovresti toccare? (risposta attesa: **zero**)

---

## FASE 2 — Collegare il modello (Azure OpenAI)

**Cosa costruiamo:** la risorsa Azure OpenAI vera, un modello "deployato" (cioè reso disponibile per essere chiamato), e la sostituzione di `EchoLLMClient` con una chiamata reale — autenticata con Managed Identity, non con una password.

### Come si fa, passo dopo passo

1. **Crea la risorsa Azure OpenAI.** "Create a resource" → cerca "Azure OpenAI" → Create. Resource group della Fase 0. Per la region: controlla prima nella pagina "Azure AI Foundry model availability" quali region offrono il modello che vuoi usare (non tutti i modelli sono disponibili ovunque). Pricing tier: Standard S0.

2. **Deploya un modello.** "Deployare" un modello significa attivarlo per l'uso, dandogli un nome che userai nel codice per chiamarlo. Apri la risorsa → link "Go to Azure AI Foundry portal" → **Deployments → + Create new deployment**. Modello: `gpt-4o-mini`. Nome deployment: `chat-deploy` (questo nome è arbitrario, lo scegli tu, e lo userai nel codice).

3. **Assegna una Managed Identity alla Function App.** Sulla Function App → **Identity** → tab **System assigned** → **On** → **Save** → conferma. Questo dice ad Azure "dai a questa Function App un'identità propria", che potrà usare per autenticarsi verso altri servizi Azure.

4. **Dai a quella identità il permesso di chiamare Azure OpenAI.** Sulla risorsa Azure OpenAI → **Access control (IAM)** → **+ Add → Add role assignment** → ruolo **"Cognitive Services OpenAI User"** → Next → "Managed identity" → **+ Select members** → seleziona la tua Function App → Review + assign. Questo è RBAC in pratica: stai dicendo "questa identità può usare (ma non modificare) questa risorsa Azure OpenAI".

5. **Installa i pacchetti Python necessari.**
   ```bash
   pip install openai azure-identity
   pip freeze > requirements.txt
   ```
   `pip install` scarica e installa le librerie nel tuo ambiente virtuale. `pip freeze > requirements.txt` salva l'elenco esatto (con versioni) di tutte le librerie installate dentro `requirements.txt`, così chiunque (o Azure stesso, in fase di deploy) può ricreare lo stesso ambiente.

6. **Crea `infrastructure/azure_openai_client.py`** (nuova cartella, allo stesso livello di `domain/` e `services/`, con un `__init__.py` dentro) col codice mostrato sotto.

7. **In `function_app.py`, cambia una riga sola:** `llm=EchoLLMClient()` diventa `llm=AzureOpenAIClient(endpoint="...", deployment="chat-deploy")`.

8. **Testa in locale.** Attenzione a un dettaglio importante: in locale, `DefaultAzureCredential` (vedi sotto) userà **la tua identità personale** (quella con cui hai fatto `az login`), non la Managed Identity — che esiste solo quando il codice gira davvero su Azure. Quindi assicurati che anche il tuo utente abbia il ruolo "Cognitive Services OpenAI User" sulla risorsa (stesso passo IAM di sopra, ma stavolta scegli "User" e seleziona te stesso).

9. **Ridistribuisci** con "Deploy to Function App", poi testa l'endpoint pubblico su Azure.

### Il codice

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
`DefaultAzureCredential` è una classe furba: prova automaticamente diversi modi di autenticarsi, in ordine (variabili d'ambiente, Managed Identity, la tua sessione `az login`, ecc.) e usa il primo che funziona. Questo è il motivo per cui **lo stesso codice** funziona sia in locale (con la tua identità) sia su Azure (con la Managed Identity), senza bisogno di scrivere due percorsi di codice diversi. Nota anche che `AzureOpenAIClient` implementa `ILLMClient` esattamente come faceva `EchoLLMClient` — è proprio questo che rende possibile lo scambio "a una riga" visto sopra.

### Cosa succede, passo dopo passo

1. Come in Fase 1, il flusso arriva fino a `self._llm.complete(message, context)` — ma ora `self._llm` è `AzureOpenAIClient`, non più la versione finta.
2. `get_bearer_token_provider` chiede un **token** valido a Microsoft Entra ID (il servizio di identità di Microsoft), usando qualunque identità sia disponibile (Managed Identity su Azure, la tua utenza in locale).
3. Il client chiama l'endpoint del deployment su Azure OpenAI, passando il messaggio e il contesto (per ora ancora vuoto — arriverà in Fase 3).
4. Azure OpenAI risponde col testo generato dal modello, che torna su fino al chiamante HTTP originale.

### Problemi comuni

| Errore | Causa | Soluzione |
|---|---|---|
| "Unauthorized" / 401 in locale | Il tuo utente non ha ancora il ruolo IAM sulla risorsa Azure OpenAI | Assegnati il ruolo "Cognitive Services OpenAI User" come utente, non solo come Managed Identity |
| "Unauthorized" su Azure dopo il deploy | L'assegnazione del ruolo alla Managed Identity non si è ancora propagata | Aspetta qualche minuto — la propagazione RBAC non è istantanea — e riprova |
| "DeploymentNotFound" | Il nome del deployment nel codice non combacia con quello creato in Azure AI Foundry | Verifica il nome esatto in Deployments e correggilo nel codice |
| Modello non disponibile in fase di creazione | Non tutte le region hanno tutti i modelli | Controlla la pagina ufficiale di disponibilità modelli prima di scegliere la region |

> **🎯 Perché per il colloquio:** "Come autentichi la chiamata a Azure OpenAI in produzione?" è una domanda quasi garantita. Risposta attesa: Managed Identity, non una API key scritta a mano nel codice.

---

## FASE 3 — Pipeline di retrieval (RAG)

**Cosa costruiamo:** una base di conoscenza reale, indicizzata su Azure AI Search con ricerca semantica/ibrida, sostituendo `EmptyRetriever` con un'implementazione vera.

### Come si fa, passo dopo passo

1. **Crea la risorsa Azure AI Search.** "Create a resource" → "Azure AI Search" → Create. Resource group della Fase 0. Pricing tier **Free** (limite: 1 indice, 50MB — più che sufficiente per questo esperimento).

2. **Prepara i documenti FAQ.** Crea una cartella `knowledge-base/` nel progetto, con 5-10 file `.md` contenenti FAQ inventate ma realistiche (es. "Come resetto la password?", "Come contatto l'assistenza?").

3. **Deploya un modello di embedding.** Un embedding (vedi glossario) trasforma un testo in un vettore di numeri, che serve per fare ricerca *per significato* invece che per parola esatta. Azure AI Foundry → Deployments → **+ Create new deployment** → modello `text-embedding-3-small`. Nome deployment: `embed-deploy`.

4. **Crea l'indice.** Sulla risorsa Azure AI Search → **Import and vectorize data** → segui il wizard: scegli la sorgente dati (puoi caricare i file direttamente) e il modello di embedding appena creato. Un "indice" è la struttura dati che Azure AI Search usa internamente per rendere le ricerche veloci.

5. **Verifica.** Sulla stessa risorsa → **Search explorer** → prova una query di test: dovresti vedere i tuoi documenti comparire tra i risultati.

6. **Crea `infrastructure/azure_search_retriever.py`** col codice mostrato sotto.

7. **In `function_app.py`, cambia un'altra riga:** `retriever=EmptyRetriever()` diventa `retriever=AzureSearchRetriever(endpoint="...", index_name="...")`.

8. **Testa end-to-end.** Fai una domanda che corrisponde a una delle tue FAQ e verifica che la risposta finale citi davvero quel contenuto — è la prova che il grounding funziona.

### Il codice

```python
# infrastructure/azure_search_retriever.py
from azure.search.documents import SearchClient
from azure.identity import DefaultAzureCredential
from domain.interfaces import IRetriever

class AzureSearchRetriever(IRetriever):
    def __init__(self, endpoint: str, index_name: str):
        self._client = SearchClient(endpoint, index_name, DefaultAzureCredential())

    def retrieve(self, query: str) -> list[str]:
        results = self._client.search(search_text=query, top=3, query_type="semantic")
        return [r["content"] for r in results]
```
Anche qui, come per `AzureOpenAIClient`, la classe implementa l'interfaccia `IRetriever` definita in `domain/interfaces.py` — è ancora la stessa Dependency Inversion vista in Fase 1: `ChatService` non deve sapere nulla di Azure AI Search, gli basta sapere che riceverà una lista di stringhe.

### Cosa succede, passo dopo passo

1. `ChatService.handle()` ora chiama `AzureSearchRetriever.retrieve(message)` invece del retriever vuoto.
2. Azure AI Search cerca i "pezzi" di documento (chunk) più rilevanti — con ricerca semantica o ibrida (che combina ricerca per parole chiave e per significato) — e li ritorna come lista di stringhe.
3. Quella lista diventa `context`, passata ad `AzureOpenAIClient.complete()` e inserita nel prompt di sistema (il messaggio "nascosto" che istruisce il modello su come comportarsi).
4. Il modello risponde "ancorato" a quel contesto, invece di inventare — è esattamente il **grounding** spiegato nel glossario.

### Problemi comuni

| Errore | Causa | Soluzione |
|---|---|---|
| Risultati di ricerca sempre vuoti | Lo script/wizard di indicizzazione non ha caricato davvero i documenti | Verifica nel Search explorer che l'indice contenga documenti, prima di dare la colpa al codice |
| Errore sul tier Free superato | Troppi documenti o indici per il limite gratuito (50MB, 1 indice) | Riduci il numero/dimensione dei documenti di test, o passa temporaneamente a un tier a pagamento |
| "query_type semantic non supportato" | Il semantic ranker non è abilitato sul tier scelto | Abilitalo dalle impostazioni della risorsa, oppure usa `query_type="simple"` per iniziare |

> **🪤 Trappola da colloquio:** la mitigazione delle allucinazioni passa dal prompt di sistema: deve istruire esplicitamente il modello a dire "non lo so" quando il contesto recuperato non è sufficiente — non va mai lasciato "indovinare" una risposta plausibile ma falsa.

---

## FASE 4 — Application Insights (osservabilità e troubleshooting)

**Cosa costruiamo:** una strumentazione (instrumentation) della pipeline per raccogliere log e metriche, e poi un esercizio pratico: rompere qualcosa di proposito e risolverlo guardando solo i log — simulando esattamente il lavoro quotidiano del ruolo.

### Come si fa, passo dopo passo

1. **Collega Application Insights.** Sulla Function App → **Application Insights** → **Turn on Application Insights** → crea una nuova risorsa (stesso resource group) → Apply.

2. **Installa il pacchetto.**
   ```bash
   pip install azure-monitor-opentelemetry
   pip freeze > requirements.txt
   ```
   OpenTelemetry è uno standard aperto per raccogliere log, metriche e tracce da un'applicazione; questo pacchetto lo collega automaticamente ad Application Insights.

3. **Crea `infrastructure/app_insights_telemetry.py`** con un helper minimale che registra un evento personalizzato (durata del retrieval, numero di token usati, esito della richiesta).

4. **Richiama l'helper dentro `ChatService`**, subito dopo ogni passaggio importante (dopo il retrieval, dopo la chiamata al modello).

5. **Genera traffico.** Fai 5-10 richieste diverse all'endpoint, così ci sono dati reali da interrogare.

6. **Interroga i log.** Sulla risorsa Application Insights → **Logs** → chiudi la finestra di esempi se compare → scrivi una query KQL:
   ```kql
   traces
   | where timestamp > ago(1h)
   | order by timestamp desc
   | take 50
   ```
   Spiegazione: `traces` è la tabella che contiene i log applicativi; `where timestamp > ago(1h)` filtra solo gli eventi dell'ultima ora; `order by timestamp desc` li ordina dal più recente; `take 50` ne mostra al massimo 50.

7. **Esercizio di troubleshooting.** In `azure_search_retriever.py`, aggiungi temporaneamente un bug volontario:
   ```python
   import time
   def retrieve(self, query: str) -> list[str]:
       time.sleep(15)
       raise TimeoutError("Simulazione timeout su Azure AI Search")
   ```
   Ridistribuisci, fai una richiesta, poi vai a **trovare** l'eccezione nei log invece di guardare il codice:
   ```kql
   exceptions
   | where timestamp > ago(15m)
   | order by timestamp desc
   ```
   Una volta trovata e "diagnosticata", rimuovi il bug e ridistribuisci di nuovo.

### Cosa succede, passo dopo passo

1. Ogni chiamata a `ChatService.handle()` genera più eventi: inizio/fine del retrieval, inizio/fine della chiamata all'LLM, eventuale eccezione.
2. Il pacchetto `azure-monitor-opentelemetry` li spedisce ad Application Insights in background, **senza bloccare** la risposta che l'utente sta aspettando.
3. Nel portale, i log diventano interrogabili con KQL dopo qualche minuto dall'invio — non è istantaneo (c'è un piccolo ritardo di ingestione).

### Problemi comuni

| Errore | Causa | Soluzione |
|---|---|---|
| Log query vuota subito dopo aver fatto una richiesta | Ingestion delay: i dati impiegano qualche minuto ad arrivare | Aspetta 2-5 minuti e riprova la query |
| Nessuna telemetria custom, solo quella di default | La connection string di Application Insights non è configurata nell'app | Verifica che `APPLICATIONINSIGHTS_CONNECTION_STRING` sia tra le variabili d'ambiente della Function App |

> **🎯 Perché per il colloquio:** il primo requisito dell'annuncio è "risoluzione di problematiche tecniche riscontrate sui chatbot attivi". Questo esercizio è letteralmente una simulazione di una giornata di lavoro nel ruolo.

---

## FASE 5 — Elaborazione asincrona (simulando una Change Request)

**Cosa costruiamo:** una seconda funzione, attivata da una coda invece che da HTTP, per gestire le richieste "complesse" senza bloccare l'utente in attesa — e senza toccare il flusso già esistente.

### Come si fa, passo dopo passo

1. **Individua lo storage account della Function App** (creato automaticamente in Fase 1, nello stesso resource group, con un nome tipo `supportchatbotXXXX`).

2. **Crea una coda.** Apri lo Storage Account → **Queues** → **+ Queue** → nome `complex-queries`. Una coda è semplicemente una lista di messaggi in attesa di essere processati, uno alla volta o in parallelo.

3. **Assicurati che Azurite sia acceso** (stesso comando `azurite` della Fase 1, in un terminale a parte).

4. **Crea la nuova function.**
   ```bash
   func new
   ```
   Scegli "Azure Queue Storage trigger", nome `process_complex_query`, coda `complex-queries`. Questo trigger fa esattamente quello che dice: si attiva ogni volta che arriva un nuovo messaggio in quella coda.

5. **Modifica l'endpoint `/api/chat`:** aggiungi un controllo semplice (es. la lunghezza del messaggio) — se la richiesta è "complessa", scrivi un messaggio sulla coda e rispondi subito con lo status `202 Accepted` e un ID di richiesta, invece di far aspettare l'utente per il risultato finale. `202` significa "ho ricevuto la tua richiesta e la sto processando, ma non è ancora finita".

6. **Scrivi la logica della queue-triggered function:** legge il messaggio dalla coda, chiama `chat_service.handle()` esattamente come prima, poi salva o logga il risultato da qualche parte.

7. **Testa in locale** con `func start` (e Azurite acceso): manda una richiesta "complessa" e verifica nei log che la queue-function parta automaticamente.

### Cosa succede, passo dopo passo

1. L'endpoint HTTP riceve la richiesta, la valuta "complessa", e scrive un messaggio JSON sulla coda `complex-queries`.
2. Risponde subito al client con `202` — l'utente non resta in attesa bloccato.
3. Il runtime di Azure Functions nota il nuovo messaggio in coda e attiva `process_complex_query` in background, in modo del tutto indipendente dalla richiesta HTTP originale (che ormai è già stata chiusa).
4. Quella function riusa lo **stesso** `chat_service`, con identica logica — nessuna duplicazione di codice.

### Problemi comuni

| Errore | Causa | Soluzione |
|---|---|---|
| "Unable to access AzureWebJobsStorage" (di nuovo) | Azurite non acceso — stesso problema della Fase 1 | Avvialo in un terminale a parte prima di `func start` |
| La queue-function non si attiva mai | Il nome della coda nel decoratore non combacia esattamente con quello creato | Controlla che i due nomi siano identici, incluse maiuscole/minuscole |

> **🎯 Perché per il colloquio:** è l'**Open/Closed Principle** (un altro principio SOLID) applicato architetturalmente: estendi il comportamento del sistema aggiungendo una nuova function, senza modificare né `ChatService` né l'endpoint esistente — il codice è "aperto all'estensione, chiuso alla modifica".

---

## FASE 6 — Widget e sistema enterprise

**Cosa costruiamo:** un piccolo widget HTML/JS che chiunque potrebbe incorporare in un sito, più uno stub (una versione semplificata di prova) di integrazione con un sistema enterprise di ticketing.

### Come si fa, passo dopo passo

1. **Crea `widget/chat-widget.html`** col codice mostrato sotto.

2. **Aprilo nel browser.** Con l'estensione VS Code "Live Server" (se non ce l'hai, installala dal pannello Extensions): tasto destro sul file → **Open with Live Server**. Live Server avvia un piccolo server locale così il widget può fare vere chiamate HTTP invece di essere aperto come semplice file.

3. **Prova a mandare un messaggio.** Se non succede nulla, apri la Console del browser (tasto `F12` → tab Console) e leggi l'errore — è lo strumento principale per il debug lato frontend.

4. **Se vedi un errore CORS** — il browser blocca chiamate verso un dominio diverso a meno che quel dominio non lo permetta esplicitamente (vedi glossario) — vai sulla tua Function App → **CORS** → aggiungi l'origine del widget (es. `http://127.0.0.1:5500` se usi Live Server, oppure `*` solo per test locali, mai in produzione) → Save.

5. **Simula il sistema enterprise.** Vai su `webhook.site` (gratuito, senza registrazione) — genera subito un URL unico che "cattura" e mostra qualunque richiesta gli arrivi. Copialo: lo useremo come finto sistema di ticketing.

6. **Crea `services/ticket_service.py`** che fa una richiesta POST a quell'URL ogni volta che manca contesto sufficiente per rispondere.

7. **Verifica** su `webhook.site` che la richiesta arrivi davvero — è la prova che l'integrazione con un sistema esterno funziona, senza doverne avere uno vero.

### Il codice

```html
<!-- widget/chat-widget.html (estratto) -->
<script>
async function sendMessage(text) {
  const res = await fetch("https://<la-tua-function>.azurewebsites.net/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text })
  });
  return res.text();
}
</script>
```
`fetch` è la funzione standard di JavaScript per fare richieste HTTP dal browser. `method: "POST"` e `headers` fanno la stessa cosa che facevano i flag di `curl` visti in Fase 1, solo scritti in JavaScript invece che da riga di comando.

### Problemi comuni

| Errore | Causa | Soluzione |
|---|---|---|
| Errore CORS in console | L'origine del widget non è tra quelle consentite sulla Function App | Aggiungila in Function App → CORS, poi ricarica la pagina |
| webhook.site non riceve nulla | L'URL generato è scaduto per inattività, o è stato copiato male | Rigenera un nuovo URL sul sito e aggiornalo nel codice |

---

## FASE 7 — PTU vs consumo

**Cosa facciamo:** non spendiamo soldi veri — è un esercizio di comprensione del modello di costo di Azure OpenAI, utile da saper spiegare a memoria in un colloquio.

### Come si fa, passo dopo passo

1. **Controlla il budget.** "Cost Management + Billing" → **Budgets** → verifica che quello creato in Fase 0 sia ancora attivo.

2. **Guarda quanto hai speso.** Stesso menu → **Cost analysis** → filtra per il resource group del progetto, per vedere solo i costi di questo esperimento.

3. **Cerca i prezzi attuali** di Azure OpenAI in modalità pay-as-you-go e delle PTU sulla pagina ufficiale Microsoft — i numeri cambiano nel tempo, quindi non fidarti di cifre "a memoria".

4. **Fai il calcolo comparativo** con carta o Excel: stima un numero realistico di richieste al mese, moltiplicalo per il costo a token (pay-as-you-go), e confrontalo col costo mensile fisso di un'unità PTU.

> **🪤 Trappola da colloquio:** le PTU hanno senso solo con volume alto e prevedibile di richieste — è capacità riservata che paghi comunque, anche se la usi poco (sotto-utilizzata). Con traffico variabile o imprevedibile, il pay-as-you-go resta quasi sempre la scelta più razionale dal punto di vista dei costi.

---

## FASE 8 — Estensioni opzionali (nice to have)

Questi due approfondimenti non sono obbligatori per il progetto principale, ma coprono le voci "nice to have" dell'annuncio.

**Microsoft Copilot Studio — confronto low-code.**
Copilot Studio è uno strumento Microsoft "low-code" (cioè richiede poco o nessun codice) per costruire chatbot tramite un'interfaccia visuale, invece di scrivere tutto a mano come abbiamo fatto qui. Prova ad andare su `copilotstudio.microsoft.com` → crea un nuovo agent → aggiungi un "topic" che risponde a una FAQ. È utile confrontare quell'esperienza con quella "a codice" che hai costruito in questo progetto, per capire quando ha senso l'una o l'altra.

**NLU / CLU — architettura ibrida.**
NLU (Natural Language Understanding) e CLU (Conversational Language Understanding, il servizio specifico di Azure) servono a classificare l'**intento** di un messaggio (es. "l'utente vuole resettare la password" vs "l'utente ha una domanda generica") prima di decidere come rispondere. Crea una risorsa "Language service" nel portale, poi apri "Language Studio" e crea un progetto CLU. L'idea di un'architettura ibrida è: classifica prima l'intento, e solo se serve davvero attiva la pipeline RAG completa — per richieste semplici, a volte basta una risposta statica, più veloce ed economica.

---

## Struttura finale del repository

Tutto piatto nella root del progetto — nessuna sottocartella `src/`, coerente con quello che hai creato passo dopo passo dalla Fase 1 in poi.

```
support-chatbot/
├── function_app.py              # entry point — adapter HTTP/Queue, resta sottile
├── domain/
│   ├── __init__.py
│   ├── interfaces.py             # ILLMClient, IRetriever, IConversationStore
│   └── models.py
├── services/
│   ├── __init__.py
│   ├── chat_service.py           # orchestrazione RAG, dipende solo da astrazioni
│   └── ticket_service.py         # escalation verso sistema enterprise
├── infrastructure/
│   ├── __init__.py
│   ├── azure_openai_client.py
│   ├── azure_search_retriever.py
│   ├── cosmos_conversation_store.py
│   └── app_insights_telemetry.py
├── widget/
│   └── chat-widget.html
├── knowledge-base/
│   └── *.md                     # documenti FAQ per l'indicizzazione RAG
├── tests/
├── requirements.txt
└── local.settings.json          # gitignored — mai committato
```

`domain/` contiene solo contratti (interfacce), `services/` la logica che orchestra quei contratti, `infrastructure/` le implementazioni concrete che parlano davvero con Azure. Questa separazione è quella discussa nella sessione precedente: le dipendenze puntano sempre verso il "dominio" (le astrazioni), mai il contrario — è il cuore pratico della Dependency Inversion applicata a un intero progetto, non solo a una singola classe.
