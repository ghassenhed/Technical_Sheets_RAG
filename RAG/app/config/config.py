"""Configuration management for the RAG system."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""
    
    # Weaviate Configuration
    weaviate_url: str = "http://localhost:8080"
    weaviate_api_key: Optional[str] = None
    
    # OpenRouter Configuration
    openrouter_api_key: str
    openrouter_model: str = "openai/gpt-oss-20b:free"
    
    # Embedding Model Configuration
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    
    # Reranker Configuration
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Retrieval Configuration
    top_k_retrieval: int = 20
    top_k_rerank: int = 5
    
    # Schema Configuration
    collection_name: str = "QcellsDocuments"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Global settings instance
settings = Settings()