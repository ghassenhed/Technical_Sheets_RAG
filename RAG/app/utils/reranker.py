"""Reranker module for improving search result relevance."""
from sentence_transformers import CrossEncoder
from typing import List, Dict, Any
from rich.console import Console

from app.config.config import settings

console = Console()


class Reranker:
    """Reranker for improving search result relevance."""
    
    def __init__(self):
        """Initialize the reranker."""
        self.model = None
    
    def load_model(self):
        """Load the cross-encoder model."""
        if not self.model:
            console.print(f"Loading reranker model: {settings.reranker_model}...")
            self.model = CrossEncoder(settings.reranker_model)
            console.print("[green]✓[/green] Reranker model loaded", style="bold")
    
    def rerank(
        self, 
        query: str, 
        documents: List[Dict[str, Any]], 
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents based on their relevance to the query.
        
        Args:
            query: The search query
            documents: List of document dictionaries with 'content' field
            top_k: Number of top results to return (default from settings)
            
        Returns:
            Reranked list of documents with added 'rerank_score' field
        """
        self.load_model()
        
        if not documents:
            return []
        
        top_k = top_k or settings.top_k_rerank
        
        # Prepare pairs for reranking
        pairs = [(query, doc['content']) for doc in documents]
        
        # Get scores
        scores = self.model.predict(pairs)
        
        # Add scores to documents
        for doc, score in zip(documents, scores):
            doc['rerank_score'] = float(score)
        
        # Sort by rerank score (descending)
        reranked = sorted(documents, key=lambda x: x['rerank_score'], reverse=True)
        
        # Return top k
        return reranked[:top_k]