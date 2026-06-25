# Architecture — Talk to your PDF

## System overview (color diagram)

![Talk to your PDF — System Architecture](./architecture-diagram.png)

## System overview (Mermaid)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {
  'primaryColor': '#3b9eff',
  'primaryTextColor': '#ffffff',
  'primaryBorderColor': '#2563a8',
  'lineColor': '#8b9cb3',
  'secondaryColor': '#34d399',
  'tertiaryColor': '#a78bfa'
}}}%%
flowchart TB
    subgraph Client["🖥️ Client — React (port 5173)"]
        UI["React UI<br/>frontend/src/App.tsx"]
    end

    subgraph DevProxy["🔀 Dev proxy — Vite"]
        PROXY["/api/* → 127.0.0.1:8000"]
    end

    subgraph API["⚡ HTTP layer — FastAPI (port 8000)"]
        MAIN["api/main.py"]
        SCHEMAS["api/schemas.py"]
    end

    subgraph Services["🧩 Service layer"]
        INGEST["IngestService"]
        CHAT["ChatService"]
    end

    subgraph IngestPipeline["📥 Ingest pipeline"]
        LOADER["document_loader<br/>PDF/TXT → text"]
        CHUNKER["chunker<br/>recursive split"]
        EMBED["embedder<br/>nomic-embed-text"]
        VS[("ChromaDB<br/>.chroma/")]
        BM25[("BM25Index<br/>.bm25/")]
    end

    subgraph QueryPipeline["💬 Query pipeline"]
        QUERY["query.py → ask()"]
        RET["retriever<br/>semantic + BM25"]
        AH["anti_hallucination<br/>relevance gates"]
        LLM["Ollama llama3"]
    end

    UI -->|"POST /upload"| PROXY
    UI -->|"POST /ask"| PROXY
    PROXY --> MAIN
    MAIN --> SCHEMAS
    MAIN --> INGEST
    MAIN --> CHAT

    INGEST --> LOADER --> CHUNKER --> EMBED --> VS
    INGEST --> BM25

    CHAT --> QUERY
    QUERY --> RET
    RET --> VS
    RET --> BM25
    QUERY --> AH
    QUERY --> LLM

    classDef frontend fill:#3b9eff,stroke:#2563a8,color:#fff
    classDef api fill:#a78bfa,stroke:#7c3aed,color:#fff
    classDef service fill:#14b8a6,stroke:#0d9488,color:#fff
    classDef ingest fill:#f97316,stroke:#ea580c,color:#fff
    classDef store fill:#22c55e,stroke:#16a34a,color:#fff
    classDef query fill:#ec4899,stroke:#db2777,color:#fff
    classDef llm fill:#8b5cf6,stroke:#6d28d9,color:#fff
    classDef guard fill:#ef4444,stroke:#dc2626,color:#fff

    class UI,PROXY frontend
    class MAIN,SCHEMAS api
    class INGEST,CHAT service
    class LOADER,CHUNKER,EMBED ingest
    class VS,BM25 store
    class QUERY,RET query
    class AH guard
    class LLM llm
```

## Layer responsibilities

| Layer | Files | Responsibility |
|-------|-------|----------------|
| UI | `frontend/src/*` | Upload PDF, ask questions, show answers + source excerpts |
| HTTP | `api/main.py`, `api/schemas.py` | REST routes, validation, JSON responses, CORS |
| Services | `rag/services/*` | Glue between FastAPI and RAG; shared `VectorStore` |
| Ingest | `document_loader`, `chunker`, `embedder`, `vector_store`, `bm25_index` | Extract → chunk → embed → index |
| Retrieve | `retriever.py` | Hybrid search: semantic top-20 → BM25 rerank → top-k |
| Answer | `query.py`, `anti_hallucination.py` | Relevance gate → LLM prompt → grounded response |

## Shared state wiring

Both services share the same in-memory `VectorStore` instance, created once in `api/main.py`:

```python
ingest_service = IngestService()
chat_service = ChatService(store=ingest_service.store)
```

On-disk indexes (`.chroma/`, `.bm25/`) persist across restarts. After upload or reset, the API reloads `BM25Index` so chat sees fresh data.

---

## Upload flow (ingestion)

```mermaid
sequenceDiagram
    actor User
    participant UI as React UI
    participant API as api/main.py
    participant IS as IngestService
    participant DL as document_loader
    participant CH as chunker
    participant EM as embedder (Ollama)
    participant VS as ChromaDB
    participant BM as BM25Index

    User->>UI: Select PDF / TXT
    UI->>API: POST /api/documents/upload
    API->>IS: save_upload() → ingest_file()
    IS->>DL: load_and_chunk(path)
    DL->>CH: chunk_text()
    CH-->>DL: list of chunks
    DL-->>IS: chunks
    IS->>EM: embed_texts(chunks)
    EM-->>IS: embeddings
    IS->>VS: add_chunks()
    IS->>BM: rebuild_from_store()
    IS-->>API: {filename, chunks_indexed, ...}
    API-->>UI: IngestResponse JSON
    UI-->>User: Show indexed chunk count
```

---

## Ask flow (RAG + anti-hallucination)

```mermaid
sequenceDiagram
    actor User
    participant UI as React UI
    participant API as api/main.py
    participant CS as ChatService
    participant Q as query.ask()
    participant R as retriever
    participant VS as ChromaDB
    participant BM as BM25Index
    participant AH as anti_hallucination
    participant LLM as Ollama llama3

    User->>UI: Enter question
    UI->>API: POST /api/chat/ask
    API->>CS: ask_question()
    CS->>Q: ask(question, store, bm25)
    Q->>R: retrieve()
    R->>VS: query (semantic top-20)
    VS-->>R: candidates + L2 distances
    R->>BM: rerank (top-k)
    BM-->>R: reranked chunks
    R-->>Q: chunks
    Q->>AH: assess_relevance(chunks)

    alt Not relevant
        AH-->>Q: refused
        Q-->>UI: declined answer + sources
    else Relevant
        AH-->>Q: pass
        Q->>LLM: chat(system + excerpts + question)
        LLM-->>Q: answer text
        Q-->>UI: answer + source excerpts
    end

    UI-->>User: Grounded answer or polite decline
```

---

## Hybrid retrieval detail

```mermaid
flowchart LR
    Q["User question"] --> E1["Embed question<br/>nomic-embed-text"]
    E1 --> S["Semantic search<br/>ChromaDB top-20"]
    S --> C["Candidate chunks<br/>+ L2 distance"]
    C --> B["BM25 rerank<br/>rank_bm25"]
    B --> K["Top-k chunks<br/>(default: 4)"]
    K --> G{"Relevance gate<br/>anti_hallucination"}
    G -->|"pass"| P["Build prompt<br/>full chunk text"]
    G -->|"fail"| R["Refuse<br/>no LLM call"]
    P --> L["Ollama llama3"]
    L --> A["Answer + citations"]
```

### Relevance gate thresholds (`rag/config.py`)

| Setting | Purpose |
|---------|---------|
| `STRONG_SEMANTIC_DISTANCE` (280) | L2 distance below this → auto-pass |
| `MAX_SEMANTIC_DISTANCE` (450) | L2 distance above this → refuse |
| `MIN_BM25_SCORE` (0.5) | Borderline semantic match needs keyword overlap |

> ChromaDB returns **L2 distance** (typically 150–350 in-document, 550+ off-topic), not a 0–1 cosine score.

---

## Project layout

```
talk-to-pdf/
├── frontend/                 # React SPA (port 5173)
│   └── src/api.ts            # fetch → /api/*
├── api/
│   ├── main.py               # FastAPI routes
│   └── schemas.py            # Request/response models
├── rag/
│   ├── config.py             # Models, chunk size, thresholds
│   ├── document_loader.py    # PDF/TXT extraction
│   ├── chunker.py            # RecursiveCharacterTextSplitter
│   ├── embedder.py           # Ollama embeddings
│   ├── vector_store.py       # ChromaDB wrapper
│   ├── bm25_index.py         # BM25 build / rerank / persist
│   ├── retriever.py          # Hybrid retrieval orchestration
│   ├── anti_hallucination.py # Relevance gates
│   ├── query.py              # ask(), prompt, LLM call
│   └── services/
│       ├── ingest_service.py
│       └── chat_service.py
├── main.py                   # CLI (same RAG pipeline)
├── data/sample-policy.txt
├── .chroma/                  # Vector DB (gitignored)
└── .bm25/                    # BM25 index (gitignored)
```

## External dependencies

```mermaid
flowchart LR
    APP["talk-to-pdf"] --> OLLAMA["Ollama<br/>localhost:11434"]
    OLLAMA --> EMB["nomic-embed-text<br/>(embeddings)"]
    OLLAMA --> LLM["llama3<br/>(chat)"]
    APP --> CHROMA["ChromaDB<br/>(local persistent)"]
```
