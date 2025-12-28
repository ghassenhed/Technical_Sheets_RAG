# RAG Pipeline for Solar Cell Datasheets

Production-ready QA system for extracting and querying technical information from solar cell documentation.

## Features

- **Smart PDF Processing**: Converts PDFs to structured Markdown with OCR support
- **Intelligent Chunking**: Section-aware segmentation with LLM-powered table conversion
- **Hybrid Retrieval**: Vector search + reranking for accurate results
- **REST API**: FastAPI endpoints for easy integration

## Architecture

```
PDF → Process & Chunk → Vector Store → Retrieve & Rerank → LLM Generate → Answer
```

![System Architecture](media/image4.png)

## Tech Stack

| Component | Technology |
|-----------|-----------|
| PDF Processing | marker-pdf + EasyOCR |
| Embedding | BAAI/bge-large-en-v1.5 |
| Reranker | cross-encoder/ms-marco-MiniLM |
| LLM | GPT-OSS-20B (OpenRouter) |
| Vector DB | Weaviate |
| API | FastAPI |

## Pipeline

### 1. Document Processing
![Processing](media/image1.png)

Converts PDFs to Markdown, preserves structure, applies OCR to images.

### 2. Intelligent Chunking
![Chunking](media/image3.png)

- Auto-detects document type (datasheet/manual)
- LLM converts tables to natural language
- Chunks by section for semantic coherence
- Extracts rich metadata

### 3. Retrieval & Generation

1. **Vector Search**: Retrieve top-20 similar chunks
2. **Reranking**: Refine to top-5 most relevant
3. **LLM Generation**: Generate answer with citations

## API Usage

### Query Endpoint

```bash
POST /query
```

**Request:**
```json
{
  "query": "What is the maximum system voltage?",
  "top_k_retrieval": 20,
  "top_k_rerank": 5
}
```

**Response:**
```json
{
  "answer": "The maximum system voltage is 1500V...",
  "sources": [{"filename": "Q.TRON_M-G3R.12+_datasheet", ...}],
  "usage": {"total_tokens": 1390}
}
```

### Other Endpoints

- `POST /search` - Vector search only
- `GET /stats` - Database statistics  
- `GET /health` - Health check

## Supported Queries

✅ Technical specs: "What is the power output?"  
✅ Installation: "How should panels be mounted?"  
✅ Comparisons: "Compare efficiency between models"  
✅ Safety: "What are the electrical requirements?"

## Future Enhancements

- Hybrid keyword + vector search
- Product name filtering for faster queries
- Support for more document types

---

**Time Spent**: ~12 hours