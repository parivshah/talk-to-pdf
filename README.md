# Talk to your PDF

Pre-interview coding challenge solution: upload a PDF, index it with hybrid RAG, and ask grounded questions with source citations.

**Stack:** Python (FastAPI), React, Ollama (`llama3` + `nomic-embed-text`), ChromaDB, BM25 reranking.

## Features

- React UI uploads PDFs → Python REST API → extract text → recursive chunking → embeddings → ChromaDB
- **Hybrid retrieval:** semantic search (top-20) → **BM25 rerank** → top-k chunks to LLM
- Answers include source excerpts (semantic rank, BM25 score, distance)
- **Anti-hallucination:** retrieval score gates + strict LLM prompt; out-of-scope questions declined
- Clear layers: `IngestService` / `retriever` / `ChatService`

## Prerequisites

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.com/) running locally

```bash
ollama pull llama3
ollama pull nomic-embed-text
```

## Setup

### Backend

```bash
cd talk-to-pdf
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

## Run

**Terminal 1 — API** (from project root):

```bash
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — React** (from `frontend/`):

```bash
npm run dev
```

Open http://localhost:5173

### Demo flow

1. Upload `data/sample-policy.txt` (or any text-based PDF)
2. Ask in-document questions:
   - "What is my wind and hail deductible?"
   - "Is mold from a slow leak covered?"
   - "What is the personal liability limit?"
3. Ask out-of-scope: "What is the capital of France?" → should be **declined**

API docs: http://127.0.0.1:8000/docs

## CLI (optional)

```bash
python main.py ingest data/sample-policy.txt
python main.py ask "What is my wind/hail deductible?" --show-sources
python main.py search "mold coverage" --no-rerank
python main.py status
```

## Architecture

![System architecture](docs/architecture-diagram.png)

See **[docs/architecture.md](docs/architecture.md)** for full Mermaid diagrams (system overview, upload flow, ask flow, hybrid retrieval).

```
React UI → FastAPI (api/main.py)
            ├── IngestService  → PDF → chunk → embed → ChromaDB + BM25
            └── ChatService    → retrieve → anti-hallucination → Ollama llama3

Question → semantic top-20 → BM25 rerank → top-4 → Llama 3
```

## Configuration (`rag/config.py`)

| Setting | Default | Purpose |
|---------|---------|---------|
| `LLM_MODEL` | `llama3` | Ollama chat model |
| `EMBED_MODEL` | `nomic-embed-text` | Ollama embedding model |
| `CHUNK_SIZE` | `500` | Recursive chunk size (chars) |
| `CHUNK_OVERLAP` | `50` | Chunk overlap |
| `RETRIEVAL_CANDIDATES` | `20` | Semantic pool before BM25 |
| `TOP_K` | `4` | Chunks sent to LLM |
| `MAX_SEMANTIC_DISTANCE` | `0.85` | Anti-hallucination threshold |
| `MIN_BM25_SCORE` | `1.0` | Anti-hallucination threshold |

### Tuning tradeoffs

- **Smaller chunks (300–400):** better precision, larger index
- **Higher top-k (6–8):** more context, more LLM tokens
- **Lower `MAX_SEMANTIC_DISTANCE`:** stricter refusal, fewer hallucinations
- **BM25 rerank:** helps exact terms like "deductible" and section numbers

## Anti-hallucination

1. Retrieval gate — if semantic distance or BM25 scores are too weak, refuse **without** calling the LLM
2. Prompt constraint — LLM must answer only from excerpts
3. Post-check — responses containing "cannot answer" flagged as `refused: true`

## Project layout

```
talk-to-pdf/
├── api/              # FastAPI REST layer
├── frontend/         # React SPA
├── rag/              # Ingest, retrieve, answer
│   └── services/
├── data/sample-policy.txt
├── main.py           # CLI
└── requirements.txt
```

## Stack choice (vs suggested C#/.NET)

Chose Python + Ollama for a fully local, key-free demo. FastAPI gives async upload handling; React matches the interview UI requirement. Architecture mirrors a .NET Web API with separate ingest/retrieve/chat services.

## Limitations

- Text-based PDFs only (no OCR)
- Single-machine, fully local
- No conversation memory or streaming
