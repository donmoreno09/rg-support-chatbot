# Fase 3 — RAG con Azure AI Search

Obiettivo: sostituire `EmptyRetriever` con un retriever reale (`AzureSearchRetriever`) che recupera contesto pertinente da una knowledge base indicizzata su Azure AI Search, completando la pipeline RAG (Retrieval-Augmented Generation).

> Nota: come per la Fase 2, questo documento segue l'esecuzione reale passo dopo passo — verrà aggiornato con gli errori incontrati e le soluzioni trovate, non solo con il piano teorico.

---

## Checklist

- [ ] Risorsa Azure AI Search creata
- [ ] Deployment del modello di embedding (`text-embedding-3-small`) su Azure OpenAI
- [ ] Documenti della knowledge base preparati (FAQ in Markdown)
- [x] Container Blob Storage creato e 10 file caricati
- [x] Indice, data source, skillset e indexer creati con il wizard "Import data" (scenario RAG) — indexer `faq-indexer`, 10/10 documenti, 0 errori
- [x] `domain/interfaces.py` esteso con `IEmbeddingClient`
- [x] `infrastructure/azure_openai_embedding_client.py` creato
- [x] `infrastructure/azure_search_retriever.py` creato
- [x] `function_app.py` aggiornato (sostituito `EmptyRetriever`)
- [ ] Managed Identity autorizzata su Azure AI Search (ruolo IAM)
- [x] Testato in locale — risposta reale basata su `reset-password.md`, non più eco o "non ho contesto sufficiente"
- [ ] Ridistribuito e testato su Azure

---

## Perché questa fase (in parole povere)

Finora il bot sa *parlare* (Fase 2, Azure OpenAI) ma non sa *niente di specifico* — `EmptyRetriever` restituisce sempre una lista vuota, quindi il modello risponde onestamente "non ho contesto sufficiente". RAG significa: prima di far generare la risposta al modello, vai a cercare in una base di documenti reale (le tue FAQ) i pezzi di testo più pertinenti alla domanda, e passali al modello come contesto. Il modello non "sa" le risposte a memoria — le legge nel contesto che gli fornisci ad ogni chiamata.

La ricerca dei pezzi pertinenti si può fare in due modi:

- **Keyword search**: cerca parole esatte (un Ctrl+F evoluto) — veloce, ma non capisce sinonimi o domande formulate diversamente dal testo originale
- **Vector search**: trasforma sia la domanda che i documenti in vettori numerici (embedding) che catturano il *significato*, poi cerca quelli più "vicini" matematicamente — capisce che "non riesco ad accedere" e "problema di login" sono la stessa cosa

Useremo **ricerca ibrida** (entrambe insieme): è lo standard in produzione, ed è ciò che ci si aspetta di saper spiegare al colloquio.

---

## Step 1 — Crea la risorsa Azure AI Search

```bash
az search service create \
  --name search-supportchatbot-don \
  --resource-group rg-support-chatbot-dev \
  --sku free \
  --location italynorth
```

- **`--name`**: diventa parte dell'endpoint pubblico (`https://search-supportchatbot-don.search.windows.net`) — deve essere univoco su tutto Azure
- **`--resource-group`**: lo stesso di tutte le altre risorse del progetto (`rg-support-chatbot-dev`), per tenerle raggruppate
- **`--sku free`**: il tier Free (F0) non costa nulla — limite di 50MB e 3 indici, più che sufficiente per una manciata di FAQ di pratica (in produzione si userebbe almeno "Basic")
- **`--location`**: usata `italynorth` — su alcune region il tier Free non è disponibile per la subscription e il wizard propone solo "Standard" senza possibilità di cambiarlo (vedi tabella problemi)

**In alternativa, da portale:**

1. Su [portal.azure.com](https://portal.azure.com), **Create a resource** → cerca **"Azure AI Search"** → **Create**
2. **Subscription**: la tua; **Resource group**: `rg-support-chatbot-dev`
3. **Service name**: `search-supportchatbot-don` (univoco su tutto Azure, diventa parte dell'URL)
4. **Location**: `Italy North` — se in una region il **Pricing tier** risulta bloccato su "Standard" senza poterlo cambiare, cambia region (vedi tabella problemi)
5. **Pricing tier**: dovrebbe mostrare **Free (50 MB, max 1 replicas, max 1 partitions, max 1 search units)** — se non è già selezionato, clicca **Change Pricing Tier**
6. **Review + create** → verifica **Estimated cost per month: $0.00** → **Create**

## Step 2 — Deploya il modello di embedding

Stessa risorsa Azure OpenAI di Fase 2 (`oai-support-chatbot`), un secondo deployment dedicato agli embedding, diverso dal modello di chat `chat-deploy`:

```bash
az cognitiveservices account deployment create \
  --name oai-support-chatbot \
  --resource-group rg-support-chatbot-dev \
  --deployment-name embed-deploy \
  --model-name text-embedding-3-small \
  --model-version "1" \
  --model-format OpenAI \
  --sku-name Standard \
  --sku-capacity 10
```

- **`--deployment-name embed-deploy`**: il nome che userai nel codice per riferirti a questo deployment — non è il nome del modello, è un'etichetta che scegli tu
- **`--model-name text-embedding-3-small`**: modello di embedding economico, sufficiente per un progetto di pratica (esiste anche `text-embedding-3-large`, più preciso ma più costoso)
- **`--sku-name Standard`**: attenzione — a differenza di `chat-deploy`, **`text-embedding-3-small` in Sweden Central è disponibile solo come `GlobalStandard`**, non come `Standard` (non è un problema di quota, il tipo di deployment proprio non esiste per questo modello in questa region). Se il comando CLI fallisce con `Standard`, usa `--sku-name GlobalStandard` — è accettabile qui perché riguarda un modello di embedding (quote più generose, dati non sensibili in un progetto di pratica), diversamente dal caso del modello di chat in Fase 2

**In alternativa, da portale:**

1. Vai sulla risorsa Azure OpenAI esistente (`oai-support-chatbot`) → **Go to Azure AI Foundry portal**
   <span>Se propone l'interfaccia "New Foundry" e blocca su una region diversa da quella della tua risorsa (stesso problema visto in Fase 2), passa a **Open in Foundry Classic**</span>
2. Menu a sinistra → **Deployments** → **+ Deploy model** → **Deploy base model**
3. Cerca **`text-embedding-3-small`** → **Confirm**
4. **Deployment name**: `embed-deploy`
5. **Deployment type**: **Global Standard** — a differenza di `chat-deploy`, `text-embedding-3-small` non è disponibile come "Standard" in Sweden Central; per un modello di embedding va bene (vedi tabella problemi)
6. **Tokens per minute rate limit**: lascia il default proposto, o abbassalo se il portale segnala limiti di capacity sulla Free Trial
7. **Deploy**

## Step 3 — Prepara la knowledge base

**Cos'è, in parole povere**: una "knowledge base" per un chatbot non è un database in senso tecnico — è semplicemente una cartella di documenti di testo che contengono le risposte reali. Il retriever (che scriviamo nello Step 8) cerca dentro questi file il pezzo più pertinente alla domanda dell'utente, e lo passa al modello come contesto.

**Perché file `.md` separati, uno per argomento**: nella pipeline RAG, ogni documento (o pezzo di documento, chiamato "chunk") viene indicizzato come unità a sé stante. Se metti tutte le FAQ in un unico file enorme, la ricerca rischia di recuperare un blocco di testo che parla di reset password *insieme* a informazioni sui resi, confondendo il modello. Un file = un argomento = un chunk pulito è la scelta più semplice per iniziare. Markdown va bene perché è testo semplice, leggibile, e si versiona bene su Git — nessuna formattazione complessa da gestire.

**Cosa fare**: crea la cartella `knowledge-base/` nella root del progetto (allo stesso livello di `domain/`, `services/`, `infrastructure/`) e mettici dentro questi 10 file già pronti — coprono i casi tipici di un chatbot di supporto tecnico/e-commerce:

| File | Argomento |
|---|---|
| `reset-password.md` | Come resettare la password |
| `tempi-consegna.md` | Tempi di consegna degli ordini |
| `contattare-supporto.md` | Come parlare con un operatore umano |
| `orari-assistenza.md` | Orari del supporto umano vs. chatbot |
| `tracciare-spedizione.md` | Come tracciare una spedizione |
| `reso-rimborso.md` | Politica di reso e rimborso |
| `metodi-pagamento.md` | Metodi di pagamento accettati |
| `modificare-dati-account.md` | Come modificare i dati dell'account |
| `problemi-login.md` | Problemi di accesso / login bloccato |
| `cancellare-ordine.md` | Come cancellare un ordine |

Ogni file segue lo stesso schema: un titolo `#` che riassume l'argomento (utile anche come metadato), seguito da 2-3 frasi con l'informazione vera e propria — abbastanza breve da non aver bisogno di essere diviso in più chunk.

Non serve altro per iniziare: questi 10 file sono già scaricabili qui sotto. Nello Step 4 li carichi su Azure, poi Azure stesso si occupa di indicizzarli.

## Step 4 — Carica i documenti su Blob Storage

**Perché qui**: la procedura guidata di indicizzazione di Azure AI Search (Step 5) legge i documenti da un "data source" nel cloud — non può leggere direttamente dal tuo computer. Il modo più semplice è caricarli su Blob Storage, il servizio di archiviazione file di Azure. Riusiamo lo storage account già creato in Fase 1 per la Function App (`stsupportchatbotdon`) — niente di nuovo da creare.

1. Su [portal.azure.com](https://portal.azure.com), vai sullo storage account **`stsupportchatbotdon`**
2. Menu a sinistra, sezione **Data storage** → **Containers**
3. **+ Container** → **Name**: `knowledge-base` → **Anonymous access level**: **Private (no anonymous access)** (i tuoi dati non devono essere pubblici) → **Create**
4. Clicca sul container appena creato (`knowledge-base`) → **Upload**
5. Seleziona i 10 file `.md` dal tuo computer (quelli scaricati allo Step 3) → **Upload**

Dovresti vedere i 10 file elencati dentro il container.

## Step 5 — Crea l'indice con "Import data" (scenario RAG)

**Perché qui**: Azure AI Search ha una procedura guidata pensata apposta per creare una pipeline RAG completa senza scrivere una riga di codice — collega un data source, genera automaticamente gli embedding tramite il tuo deployment Azure OpenAI, e crea da solo indice, schema (incluso il campo vettoriale), e il meccanismo che tiene tutto sincronizzato (l'"indexer"). Questa è la strada davvero "tutta da portale", più realistica di comporre a mano un JSON di schema.

> Nota: sul portale nella tua versione questa funzionalità **non** è un pulsante separato "Import and vectorize data" come previsto inizialmente — è integrata nel wizard classico **"Import data"**. La procedura reale, verificata passo passo:

1. Vai sulla risorsa Azure AI Search (`search-supportchatbot-don`) → toolbar in alto → **Import data**
2. **Choose a data source** → **Azure Blob Storage**
3. **What scenario are you targeting?** → scegli **RAG** (non "Keyword search", che non genera vettori; non "Multimodal RAG", pensato per PDF/immagini con diagrammi — noi abbiamo solo testo semplice)
4. Si apre un wizard a step (**Connect to your data** → **Vectorize your text** → **Vectorize your images** → **Advanced settings** → **Review and create**). Nel primo step, **Configure your Azure Blob Storage**:
   - **Storage account**: `stsupportchatbotdon`
   - **Blob container**: `knowledge-base`
   - **Blob folder**: vuoto (i file stanno nella radice del container)
   - **Parsing mode**: `Default` (va bene per testo semplice)
   - **Enable deletion tracking**: deselezionato (serve per sincronizzare cancellazioni in scenari con aggiornamenti ricorrenti, non ci serve per un indice statico di pratica)
   - **Authenticate using managed identity**: **spuntato** — coerente con l'approccio "nessuna chiave" di tutto il progetto. Se il wizard segnala che la Managed Identity non è abilitata sulla risorsa Search, abilitala da **Identity** nel menu della risorsa (stessa procedura fatta in Fase 2 per la Function App), poi assegna il ruolo **Storage Blob Data Reader** su `stsupportchatbotdon` a quell'identità (vedi tabella problemi se emerge)
   - **Next**
5. **Vectorize your text**:
   - **Kind**: `Foundry resource (Microsoft Foundry/Azure OpenAI)` — copre anche le risorse Azure OpenAI "classiche" come la nostra
   - **Microsoft Foundry service/project**: `oai-support-chatbot`
   - **Model deployment**: `embed-deploy`
   - **Authentication type**: **System assigned identity** (non "API key") — coerente con l'approccio senza chiavi di tutto il progetto. Se dà lo stesso errore di autorizzazione visto per lo storage, assegna il ruolo **Cognitive Services OpenAI User** su `oai-support-chatbot` alla Managed Identity di `search-supportchatbot-don` (vedi tabella problemi)
   - Spunta la conferma sui costi aggiuntivi (obbligatoria — Azure OpenAI è pay-per-use)
   - **Next**
6. **Vectorize your images**: lascia disattivato / **"I don't want to vectorize my images"** — non abbiamo immagini nella knowledge base → **Next**
7. **Advanced settings**:
   - **Enable semantic ranker**: **deselezionato** — il tier Free (F0) non include questa feature, lasciarlo attivo rischia un errore in fase di creazione (vedi tabella problemi)
   - **Schedule**: **Once** (indicizza subito, non serve un aggiornamento periodico per un progetto di pratica statico)
   - **Next**
8. **Review and create**: qui, non nello step precedente, trovi il campo che determina il nome dell'indice: **Objects name prefix**. Il wizard non fa scegliere un "Index name" diretto — genera indice, indexer, data source e skillset tutti con questo prefisso. Cambia il valore di default (un timestamp poco leggibile tipo `rag-1789546541600`) in qualcosa di significativo, es. `faq` → verifica il riepilogo (Azure OpenAI service, deployment model, semantic ranker disabled) → **Create**
   <span>Conferma reale: con prefisso `faq`, l'indice risultante si chiama semplicemente **`faq`** — il prefisso diventa il nome diretto, senza suffisso `-index` aggiunto</span>

La procedura crea in automatico quattro cose (utile saperle nominare al colloquio):
- il **data source** (il collegamento al container Blob)
- l'**indice** `faq-index` (schema con `content` e il campo vettoriale, generato da Azure stesso)
- lo **skillset** (la "ricetta" che dice ad Azure: dividi il testo in chunk, poi chiama `embed-deploy` per ogni chunk)
- l'**indexer** (il processo che esegue lo skillset e scrive i risultati nell'indice — lo trovi in **Indexers** nel menu a sinistra, con lo stato dell'ultima esecuzione)

**Verifica**: aspetta che l'indexer finisca (stato "Success" in **Indexers**), poi vai su **Indexes** → `faq-index` → **Search explorer** → digita una query di prova (es. "password") → controlla che tra i risultati compaia contenuto dal file `reset-password.md`.

## Step 6 — Estendi le interfacce (Interface Segregation)

In `domain/interfaces.py`, aggiungi un'astrazione **separata** da `ILLMClient` — generare testo e generare embedding sono due responsabilità diverse, un client non deve dipendere da metodi che non usa:

```python
class IEmbeddingClient(Protocol):
    def embed(self, text: str) -> list[float]: ...
```

## Step 7 — `infrastructure/azure_openai_embedding_client.py`

```python
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from domain.interfaces import IEmbeddingClient

class AzureOpenAIEmbeddingClient(IEmbeddingClient):
    def __init__(self, endpoint: str, deployment: str):
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        )
        self._client = AzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version="2024-10-21",
        )
        self._deployment = deployment

    def embed(self, text: str) -> list[float]:
        result = self._client.embeddings.create(model=self._deployment, input=text)
        return result.data[0].embedding
```

Stessa autenticazione Managed Identity di `AzureOpenAIClient` (Fase 2) — nessuna chiave, stesso pattern del token provider.

## Step 8 — `infrastructure/azure_search_retriever.py`

Prima di scrivere il codice, installa il pacchetto che il retriever userà per interrogare l'indice (venv attivo):
```bash
pip install azure-search-documents
pip freeze > requirements.txt
```
Il secondo comando rigenera `requirements.txt` con tutto ciò che è installato nel venv in quel momento — stessa identica procedura di Fase 2 (Step 5): non si aggiunge una riga a mano, si sovrascrive il file con `pip freeze`, così `requirements.txt` conterrà sia i pacchetti di Fase 2 (`openai`, `azure-identity`) sia il nuovo `azure-search-documents`, con le versioni esatte installate.

```python
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.identity import DefaultAzureCredential
from domain.interfaces import IRetriever, IEmbeddingClient

class AzureSearchRetriever(IRetriever):
    def __init__(self, endpoint: str, index_name: str, embedding_client: IEmbeddingClient):
        self._client = SearchClient(endpoint, index_name, DefaultAzureCredential())
        self._embedding_client = embedding_client

    def retrieve(self, query: str) -> list[str]:
        vector = self._embedding_client.embed(query)
        vector_query = VectorizedQuery(
            vector=vector, k_nearest_neighbors=3, fields="text_vector"
        )
        results = self._client.search(
            search_text=query,               # componente keyword
            vector_queries=[vector_query],   # componente vettoriale → ricerca ibrida
            top=3,
        )
        return [r["chunk"] for r in results]
```

Nota: i nomi dei campi (`chunk`, `text_vector`) sono quelli generati automaticamente dal wizard "Import data" nello Step 5, diversi dai nomi che avremmo scelto scrivendo lo schema a mano (`content`, `content_vector`) — l'indice esistente comanda, il codice si adatta.

Nota architetturale: `AzureSearchRetriever` dipende da `IEmbeddingClient` (l'astrazione), non da `AzureOpenAIEmbeddingClient` direttamente — è di nuovo Dependency Inversion, la stessa ragione per cui in Fase 2 `ChatService` non ha mai saputo dell'esistenza di Azure OpenAI.

## Step 9 — Collega tutto in `function_app.py`

```python
from infrastructure.azure_search_retriever import AzureSearchRetriever
from infrastructure.azure_openai_embedding_client import AzureOpenAIEmbeddingClient

embedding_client = AzureOpenAIEmbeddingClient(
    endpoint="https://oai-support-chatbot.openai.azure.com/",
    deployment="embed-deploy",
)

retriever = AzureSearchRetriever(
    endpoint="https://search-supportchatbot-don.search.windows.net",
    index_name="faq",
    embedding_client=embedding_client,
)
```

Nel punto dove viene istanziato `ChatService`, sostituisci `retriever=EmptyRetriever()` con `retriever=retriever`. Di nuovo una riga sola — `EmptyRetriever` va cancellato come classe morta, stessa pulizia fatta con `EchoLLMClient` in Fase 2.

## Step 10 — Autorizza la Managed Identity su Azure AI Search

Come in Fase 2 con Azure OpenAI: risorsa Azure AI Search → **Access control (IAM)** → **+ Add role assignment** → ruolo **Search Index Data Reader** → assegna alla Managed Identity della Function App (`func-supportchatbot-don`). Per i test in locale, assegna lo stesso ruolo anche al tuo utente.

## Step 11 — Testa in locale, poi ridistribuisci

`func start` → prova con una domanda che matcha una delle tue FAQ (es. "come resetto la password?") → la risposta dovrebbe ora citare il contenuto reale, non più "non ho contesto sufficiente". Poi redeploy e test sull'endpoint pubblico, stessa procedura delle fasi precedenti.

---

## Problemi incontrati e soluzioni

*(si popola mano a mano che procediamo — qui finiranno gli errori reali, non quelli previsti a tavolino)*

| Errore | Causa | Soluzione |
|---|---|---|
| **Pricing tier** bloccato su "Standard" nel wizard di creazione, "Change Pricing Tier" non permette di selezionare "Free" | La region scelta inizialmente non aveva capacity Free disponibile per questa subscription | Cambiata **Location** in **Italy North** — con quella region il tier Free è diventato selezionabile |
| Selezionando "Standard" come Deployment type per `text-embedding-3-small` in Sweden Central, la region non risulta più disponibile | Quel modello, in quella region, è esposto solo come "Global Standard" — non è un limite di quota ma di disponibilità del tipo di deployment per quel modello specifico | Usato **Global Standard** per il deployment dell'embedding — accettabile perché modello leggero e dati non sensibili (diverso dal caso del modello di chat in Fase 2) |
| "This request is not authorized to perform this operation using this permission" cliccando Next nello step "Connect to your data" del wizard Import data | La Managed Identity della risorsa Search non ha ancora un ruolo IAM sullo storage account — "Authenticate using managed identity" da solo non basta, va autorizzata esplicitamente | Assegnato il ruolo **Storage Blob Data Reader** su `stsupportchatbotdon` alla Managed Identity di `search-supportchatbot-don`, da **Access control (IAM)** dello storage account |
| Test in locale corretto (risposta reale RAG), ma l'endpoint pubblico rispondeva ancora con l'eco di Fase 1 (`"hai detto: ..."`) | Il codice locale non era mai stato ridistribuito dopo le modifiche di Fase 2/3 — l'endpoint pubblico girava ancora sul primissimo deploy di Fase 1 | Ridistribuito con "Deploy to Function App" da VS Code (stessa procedura di Fase 1/2), dopo aver verificato che la Managed Identity della Function App avesse il ruolo Search Index Data Reader sulla risorsa Search |

---

## 🎯 Perché per il colloquio

- **"Come mitighi le allucinazioni in una pipeline RAG?"** — risposta attesa: il retrieval da solo non basta, va accoppiato a un prompt di sistema che istruisce esplicitamente il modello a dire "non lo so" se il contesto recuperato non è sufficiente (già fatto in `AzureOpenAIClient`, Fase 2).
- **"Perché ricerca ibrida e non solo vettoriale?"** — la ricerca keyword intercetta ancora match esatti (nomi di prodotto, codici errore) che la ricerca semantica a volte diluisce; insieme coprono più casi.
- **Checkpoint architetturale**: perché `IEmbeddingClient` è un'interfaccia separata da `ILLMClient`, anche se in questo progetto le implementa la stessa risorsa Azure OpenAI? Interface Segregation: generare testo e generare vettori sono due responsabilità diverse — un domani potresti voler usare un provider di embedding diverso da quello di chat senza toccare `ILLMClient`.
- **"Perché non hai usato LangChain?"** — risposta attesa: `IRetriever`/`ILLMClient`/`IEmbeddingClient` ottengono già la stessa separazione di responsabilità che offrirebbe un framework di orchestrazione, ma costruendola a mano si controlla ogni dettaglio (autenticazione Managed Identity, costruzione della query ibrida) invece di lasciarlo opaco dietro un'astrazione di terzi — più adatto a dimostrare competenza sulla piattaforma Azure nuda, come richiesto dall'annuncio. Conoscere LangChain e Semantic Kernel (l'equivalente Microsoft) a livello concettuale resta comunque utile da menzionare.
