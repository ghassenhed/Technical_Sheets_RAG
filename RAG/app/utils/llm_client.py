"""LLM client for text generation using OpenRouter."""
from openai import OpenAI
from typing import List, Dict, Any, Optional
from rich.console import Console

from app.config.config import settings

console = Console()


class LLMClient:
    """Client for interacting with LLMs via OpenRouter."""
    
    def __init__(self):
        """Initialize the LLM client."""
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
        )
    
    def generate_response(
        self,
        query: str,
        context_chunks: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Generate a response using the LLM with retrieved context.
        
        Args:
            query: User's question
            context_chunks: Retrieved and reranked document chunks
            system_prompt: Optional custom system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            
        Returns:
            Dictionary with response and metadata
        """
        try:
            # Build context from chunks
            context = self._build_context(context_chunks)
            
            # Default system prompt if not provided
            if not system_prompt:
                system_prompt = """You are a helpful assistant that answers questions about Qcells solar panel products based on the provided documentation.

Your responsibilities:
- Answer questions accurately using only the information from the provided context
- If the answer is not in the context, clearly state that you don't have that information
- Cite specific sources when providing technical specifications or important details
- Be concise but thorough in your explanations
- Use clear, professional language
- Do not use any Markdown, or formatting symbols in your responses.

Context format:
Each piece of context includes:
- Content: The actual text from the documentation
- Source: The document filename
- Document Type: The type of document (datasheet, manual, etc.)"""
            
            # Build the user message with context
            user_message = f"""Context from documentation:

{context}

---

Question: {query}

Please answer the question based on the context provided above. If the answer requires information not present in the context, please state that clearly."""
            
            # Generate response
            response = self.client.chat.completions.create(
                model=settings.openrouter_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            return {
                "answer": response.choices[0].message.content,
                "model": settings.openrouter_model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                "sources": self._extract_sources(context_chunks)
            }
            
        except Exception as e:
            console.print(f"[red]✗[/red] LLM generation failed: {e}", style="bold red")
            return {
                "answer": f"Error generating response: {str(e)}",
                "model": settings.openrouter_model,
                "usage": {},
                "sources": []
            }
    
    def _build_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Build formatted context string from chunks."""
        context_parts = []
        
        for i, chunk in enumerate(chunks, 1):
            context_part = f"""[Source {i}]
Document: {chunk.get('source_file', 'Unknown')}
Type: {chunk.get('document_type', 'Unknown')}
Relevance Score: {chunk.get('rerank_score', 0):.4f}

{chunk.get('content', '')}

---"""
            context_parts.append(context_part)
        
        return "\n".join(context_parts)
    
    def _extract_sources(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract unique sources from chunks."""
        sources = {}
        
        for chunk in chunks:
            source_file = chunk.get('source_file', 'Unknown')
            if source_file not in sources:
                sources[source_file] = {
                    "filename": source_file,
                    "document_type": chunk.get('document_type', 'Unknown'),
                    "chunks_used": 0
                }
            sources[source_file]["chunks_used"] += 1
        
        return list(sources.values())