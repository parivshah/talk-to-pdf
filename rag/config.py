from pathlib import Path

LLM_MODEL = "llama3"
EMBED_MODEL = "nomic-embed-text"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
RETRIEVAL_CANDIDATES = 20
TOP_K = 4
MAX_EXCERPT_CHARS = 500

MAX_SEMANTIC_DISTANCE = 0.85
MIN_BM25_SCORE = 1.0

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = PROJECT_ROOT / ".chroma"
DATA_DIR = PROJECT_ROOT / "data"
BM25_DIR = PROJECT_ROOT / ".bm25"
UPLOAD_DIR = PROJECT_ROOT / "uploads"
COLLECTION_NAME = "document_chunks"
