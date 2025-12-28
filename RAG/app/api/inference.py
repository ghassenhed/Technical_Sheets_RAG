"""FastAPI application for RAG system REST API."""
from fastapi import FastAPI, HTTPException, Query, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from pathlib import Path

from app.utils.weaviate_client import WeaviateClient
from app.utils.reranker import Reranker
from app.utils.llm_client import LLMClient
from app.config.config import settings


# Global instances
weaviate_client = None
reranker = None
llm_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI app."""
    global weaviate_client, reranker, llm_client
    
    # Startup
    weaviate_client = WeaviateClient()
    weaviate_client.connect()
    reranker = Reranker()
    llm_client = LLMClient()
    
    yield
    
    # Shutdown
    if weaviate_client:
        weaviate_client.close()

router = APIRouter(prefix="/ask", tags=["RAG"])


# Request/Response Models
class SearchRequest(BaseModel):
    """Request model for search endpoint."""
    query: str = Field(..., description="Search query")
    limit: Optional[int] = Field(None, description="Number of results to return")


class QueryRequest(BaseModel):
    """Request model for query endpoint."""
    query: str = Field(..., description="User's question")
    top_k_retrieval: Optional[int] = Field(None, description="Number of chunks to retrieve")
    top_k_rerank: Optional[int] = Field(None, description="Number of chunks after reranking")
    temperature: Optional[float] = Field(0.7, description="LLM temperature")
    max_tokens: Optional[int] = Field(2000, description="Maximum tokens in response")
    system_prompt: Optional[str] = Field(None, description="Custom system prompt")


class ChunkResponse(BaseModel):
    """Response model for a single chunk."""
    uuid: str
    content: str
    source_file: str
    chunk_index: int
    document_type: str
    metadata: Dict[str, Any]
    distance: Optional[float] = None
    rerank_score: Optional[float] = None


class SearchResponse(BaseModel):
    """Response model for search endpoint."""
    query: str
    results: List[ChunkResponse]
    total_results: int


class QueryResponse(BaseModel):
    """Response model for query endpoint."""
    query: str
    answer: str
    sources: List[Dict[str, Any]]
    model: str
    usage: Dict[str, Any]
    context_chunks: List[ChunkResponse]


class StatsResponse(BaseModel):
    """Response model for stats endpoint."""
    total_chunks: int
    collection_name: str


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    weaviate_connected: bool


# Endpoints
@router.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Qcells RAG API",
        "version": "1.0.0",
        "description": "API for querying Qcells solar panel documentation",
        "endpoints": {
            "health": "/health",
            "stats": "/stats",
            "search": "/search",
            "query": "/query",
            "ui": "/askme"
        }
    }


@router.get("/askme", response_class=HTMLResponse, tags=["UI"])
async def query_ui():
    """
    Web UI for querying the RAG system.
    
    This endpoint serves an interactive HTML interface where users can:
    - Ask questions about Qcells solar panel documentation
    - Configure retrieval parameters
    - View formatted answers with sources
    """
    template_path = Path(__file__).parent.parent / "templates" / "query_ui.html"
    
    if not template_path.exists():
        raise HTTPException(
            status_code=500, 
            detail=f"Template not found at {template_path}"
        )
    
    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    return HTMLResponse(content=html_content)


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Check API and Weaviate health."""
    weaviate_connected = weaviate_client is not None and weaviate_client.client is not None
    
    return {
        "status": "healthy" if weaviate_connected else "unhealthy",
        "weaviate_connected": weaviate_connected
    }


@router.get("/stats", response_model=StatsResponse, tags=["Info"])
async def get_stats():
    """Get database statistics."""
    if not weaviate_client:
        raise HTTPException(status_code=503, detail="Weaviate client not initialized")
    
    try:
        stats = weaviate_client.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.post("/search", response_model=SearchResponse, tags=["Search"])
async def search(request: SearchRequest):
    """
    Search for similar document chunks using vector similarity.
    
    This endpoint retrieves chunks based on semantic similarity without
    reranking or LLM generation.
    """
    if not weaviate_client:
        raise HTTPException(status_code=503, detail="Weaviate client not initialized")
    
    try:
        results = weaviate_client.search(
            query=request.query,
            limit=request.limit
        )
        
        return {
            "query": request.query,
            "results": results,
            "total_results": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/query", response_model=QueryResponse, tags=["Query"])
async def query(request: QueryRequest):
    """
    Query the system with retrieval, reranking, and LLM generation.
    
    This is the main RAG endpoint that:
    1. Retrieves relevant chunks using vector similarity
    2. Reranks chunks for better relevance
    3. Generates a response using an LLM with the top chunks as context
    """
    if not weaviate_client:
        raise HTTPException(status_code=503, detail="Weaviate client not initialized")
    
    try:
        # Step 1: Retrieve
        top_k_retrieval = request.top_k_retrieval or settings.top_k_retrieval
        results = weaviate_client.search(query=request.query, limit=top_k_retrieval)
        
        if not results:
            return {
                "query": request.query,
                "answer": "No relevant information found in the documentation.",
                "sources": [],
                "model": settings.openrouter_model,
                "usage": {},
                "context_chunks": []
            }
        
        # Step 2: Rerank
        top_k_rerank = request.top_k_rerank or settings.top_k_rerank
        reranked_results = reranker.rerank(
            query=request.query,
            documents=results,
            top_k=top_k_rerank
        )
        
        # Step 3: Generate response
        response = llm_client.generate_response(
            query=request.query,
            context_chunks=reranked_results,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        return {
            "query": request.query,
            "answer": response["answer"],
            "sources": response["sources"],
            "model": response["model"],
            "usage": response["usage"],
            "context_chunks": reranked_results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.get("/config", tags=["Info"])
async def get_config():
    """Get current system configuration."""
    return {
        "weaviate_url": settings.weaviate_url,
        "collection_name": settings.collection_name,
        "embedding_model": settings.embedding_model,
        "reranker_model": settings.reranker_model,
        "llm_model": settings.openrouter_model,
        "top_k_retrieval": settings.top_k_retrieval,
        "top_k_rerank": settings.top_k_rerank
    }