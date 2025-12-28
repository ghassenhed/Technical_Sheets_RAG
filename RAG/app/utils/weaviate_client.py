"""Weaviate client for vector database operations."""
import weaviate
from weaviate.classes.config import Configure, Property, DataType
from weaviate.classes.query import MetadataQuery
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
import json
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from app.config.config import settings

console = Console()


class WeaviateClient:
    """Client for interacting with Weaviate vector database."""
    
    def __init__(self):
        """Initialize Weaviate client."""
        self.client = None
        self.embedding_model = None
        
    def connect(self) -> bool:
        """Connect to Weaviate instance (v4+ compatible)."""
        try:
            http_host = "weaviate"
            grpc_host = "weaviate"
            http_port = 8080
            grpc_port = 50051
            secure = False

            if settings.weaviate_api_key:
                self.client = weaviate.connect_to_custom(
                    http_host=http_host,
                    http_port=http_port,
                    http_secure=secure,
                    grpc_host=grpc_host,
                    grpc_port=grpc_port,
                    grpc_secure=secure,
                    auth_credentials=AuthApiKey(settings.weaviate_api_key)
                )
            else:
                self.client = weaviate.connect_to_custom(
                    http_host=http_host,
                    http_port=http_port,
                    http_secure=secure,
                    grpc_host=grpc_host,
                    grpc_port=grpc_port,
                    grpc_secure=secure,
                )

            print("✅ Connected to Weaviate successfully.")
            return True

        except Exception as e:
            print(f"❌ Failed to connect to Weaviate: {e}")
            self.client = None
            return False
            
    
    def close(self):
        """Close Weaviate connection."""
        if self.client:
            self.client.close()
    
    def load_embedding_model(self):
        """Load the sentence transformer model for embeddings."""
        if not self.embedding_model:
            console.print(f"Loading embedding model: {settings.embedding_model}...")
            self.embedding_model = SentenceTransformer(settings.embedding_model)
            console.print("[green]✓[/green] Embedding model loaded", style="bold")
    
    def create_schema(self, delete_existing: bool = False):
        """Create or update the Weaviate schema."""
        try:
            collection_name = settings.collection_name
            
            # Delete existing collection if requested
            if delete_existing and self.client.collections.exists(collection_name):
                self.client.collections.delete(collection_name)
                console.print(f"[yellow]⚠[/yellow] Deleted existing collection: {collection_name}")
            
            # Create collection if it doesn't exist
            if not self.client.collections.exists(collection_name):
                self.client.collections.create(
                    name=collection_name,
                    properties=[
                        Property(name="content", data_type=DataType.TEXT),
                        Property(name="source_file", data_type=DataType.TEXT),
                        Property(name="chunk_index", data_type=DataType.INT),
                        Property(name="document_type", data_type=DataType.TEXT),
                        Property(name="metadata", data_type=DataType.TEXT),
                    ],
                    vectorizer_config=Configure.Vectorizer.none(),
                )
                console.print(f"[green]✓[/green] Created collection: {collection_name}", style="bold")
            else:
                console.print(f"[blue]ℹ[/blue] Collection already exists: {collection_name}")
                
            return True
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to create schema: {e}", style="bold red")
            return False
    
    def index_chunks(self, chunks_dir: str = "app/chuncks") -> int:
        """Index all chunks from the chunks directory."""
        try:
            self.load_embedding_model()
            chunks_path = Path(chunks_dir)
            
            if not chunks_path.exists():
                console.print(f"[red]✗[/red] Chunks directory not found: {chunks_dir}", style="bold red")
                return 0
            
            # Get all JSON files
            chunk_files = list(chunks_path.glob("*_chunked.json"))
            
            if not chunk_files:
                console.print(f"[yellow]⚠[/yellow] No chunk files found in {chunks_dir}")
                return 0
            
            collection = self.client.collections.get(settings.collection_name)
            total_indexed = 0
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console
            ) as progress:
                
                task = progress.add_task(
                    f"[cyan]Indexing chunks...", 
                    total=len(chunk_files)
                )
                
                for chunk_file in chunk_files:
                    try:
                        with open(chunk_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        chunks = data.get('chunks', [])
                        source_file = data.get('source_file', chunk_file.stem)
                        document_type = data.get('document_type', 'unknown')
                        
                        # Prepare batch insert
                        objects = []
                        for chunk in chunks:
                            content = chunk.get('text', '')
                            if not content.strip():
                                continue
                            
                            # Generate embedding
                            embedding = self.embedding_model.encode(content).tolist()
                            
                            objects.append({
                                "properties": {
                                    "content": content,
                                    "source_file": source_file,
                                    "chunk_index": chunk.get('chunk_index', 0),
                                    "document_type": document_type,
                                    "metadata": json.dumps(chunk.get('metadata', {}))
                                },
                                "vector": embedding
                            })
                        
                        # Batch insert
                        if objects:
                            with collection.batch.dynamic() as batch:
                                for obj in objects:
                                    batch.add_object(
                                        properties=obj["properties"],
                                        vector=obj["vector"]
                                    )
                            
                            total_indexed += len(objects)
                        
                        progress.update(task, advance=1)
                        
                    except Exception as e:
                        console.print(f"[red]✗[/red] Error indexing {chunk_file.name}: {e}")
                        continue
            
            console.print(f"[green]✓[/green] Successfully indexed {total_indexed} chunks", style="bold green")
            return total_indexed
            
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to index chunks: {e}", style="bold red")
            return 0
    
    def search(self, query: str, limit: int = None) -> List[Dict[str, Any]]:
        """Search for similar chunks using vector similarity."""
        try:
            self.load_embedding_model()
            
            # Generate query embedding
            query_embedding = self.embedding_model.encode(query).tolist()
            
            # Search
            collection = self.client.collections.get(settings.collection_name)
            response = collection.query.near_vector(
                near_vector=query_embedding,
                limit=limit or settings.top_k_retrieval,
                return_metadata=MetadataQuery(distance=True)
            )
            
            results = []
            for obj in response.objects:
                results.append({
                    "uuid": str(obj.uuid),
                    "content": obj.properties.get("content", ""),
                    "source_file": obj.properties.get("source_file", ""),
                    "chunk_index": obj.properties.get("chunk_index", 0),
                    "document_type": obj.properties.get("document_type", ""),
                    "metadata": json.loads(obj.properties.get("metadata", "{}")),
                    "distance": obj.metadata.distance
                })
            
            return results
            
        except Exception as e:
            console.print(f"[red]✗[/red] Search failed: {e}", style="bold red")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the indexed data."""
        try:
            collection = self.client.collections.get(settings.collection_name)
            aggregate = collection.aggregate.over_all(total_count=True)
            
            return {
                "total_chunks": aggregate.total_count,
                "collection_name": settings.collection_name
            }
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to get stats: {e}", style="bold red")
            return {}