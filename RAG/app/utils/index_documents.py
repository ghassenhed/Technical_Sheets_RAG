"""
Standalone script for indexing documents into Weaviate.
Run this offline to embed and store documents before starting the API.

Usage:
    python index_documents.py                           # Index from default directory
    python index_documents.py --chunks-dir /path/to/chunks  # Custom directory
    python index_documents.py --delete-existing         # Delete existing data first
    python index_documents.py --batch-size 100          # Custom batch size
"""
import argparse
import json
import sys
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.table import Table

from app.utils.weaviate_client import WeaviateClient
from app.config.config import settings

console = Console()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Index Qcells documentation chunks into Weaviate vector database"
    )
    parser.add_argument(
        '--chunks-dir',
        type=str,
        default='app/chuncks',
        help='Directory containing chunked JSON files (default: app/chuncks)'
    )
    parser.add_argument(
        '--delete-existing',
        action='store_true',
        help='Delete existing collection and recreate schema'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Batch size for indexing (default: 100)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed progress information'
    )
    
    return parser.parse_args()


def display_header():
    """Display script header."""
    console.print(Panel.fit(
        "[bold cyan]Qcells RAG System - Document Indexing[/bold cyan]\n"
        "[dim]Embedding and storing documents in Weaviate[/dim]",
        border_style="cyan"
    ))
    console.print()


def check_environment():
    """Check if environment is properly configured."""
    console.print("[cyan]→[/cyan] Checking environment configuration...")
    
    issues = []
    
    # Check Weaviate URL
    if not settings.weaviate_url:
        issues.append("WEAVIATE_URL not set")
    
    # Check embedding model
    if not settings.embedding_model:
        issues.append("EMBEDDING_MODEL not set")
    
    if issues:
        console.print("[red]✗[/red] Configuration issues found:", style="bold red")
        for issue in issues:
            console.print(f"  • {issue}")
        console.print("\n[yellow]Please check your .env file[/yellow]")
        return False
    
    console.print("[green]✓[/green] Environment configuration OK")
    return True


def connect_to_weaviate():
    """Connect to Weaviate instance."""
    console.print("[cyan]→[/cyan] Connecting to Weaviate...")
    
    client = WeaviateClient()
    if not client.connect():
        console.print("[red]✗[/red] Failed to connect to Weaviate", style="bold red")
        console.print("[yellow]Make sure Weaviate is running:[/yellow]")
        console.print("  docker-compose up -d")
        return None
    
    return client



def setup_schema(client, delete_existing=False):
    """Create or update the Weaviate schema."""
    console.print(f"[cyan]→[/cyan] {'Recreating' if delete_existing else 'Setting up'} schema...")
    
    if not client.create_schema(delete_existing=delete_existing):
        console.print("[red]✗[/red] Failed to setup schema", style="bold red")
        return False
    
    return True


def find_chunk_files(chunks_dir):
    """Find all chunk files in the directory."""
    console.print(f"[cyan]→[/cyan] Scanning for chunk files in {chunks_dir}...")
    
    chunks_path = Path(chunks_dir)
    
    if not chunks_path.exists():
        console.print(f"[red]✗[/red] Directory not found: {chunks_dir}", style="bold red")
        return []
    
    chunk_files = list(chunks_path.glob("*_chunked.json"))
    
    if not chunk_files:
        console.print(f"[yellow]⚠[/yellow] No chunk files found in {chunks_dir}")
        console.print("[dim]Expected files with pattern: *_chunked.json[/dim]")
        return []
    
    console.print(f"[green]✓[/green] Found {len(chunk_files)} chunk file(s)")
    return chunk_files


def index_documents(client, chunk_files, verbose=False):
    """Index all chunk files into Weaviate."""
    console.print(f"[cyan]→[/cyan] Starting indexing process...")
    console.print()
    
    total_chunks = 0
    total_indexed = 0
    failed_files = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        
        main_task = progress.add_task(
            "[cyan]Indexing files...",
            total=len(chunk_files)
        )
        
        for chunk_file in chunk_files:
            try:
                # Load chunk file
                with open(chunk_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                chunks = data.get('chunks', [])
                source_file = data.get('metadata', chunk_file.stem)["source_file"]
                document_type = data.get('metadata', 'unknown')["document_type"]
                
                if not chunks:
                    if verbose:
                        console.print(f"[yellow]⚠[/yellow] No chunks in {chunk_file.name}")
                    progress.update(main_task, advance=1)
                    continue
                
                total_chunks += len(chunks)
                
                # Prepare batch insert
                collection = client.client.collections.get(settings.collection_name)
                objects = []
                
                for chunk in chunks:
                    content = chunk.get('content', '')
                    if not content.strip():
                        continue
                    
                    # Generate embedding
                    embedding = client.embedding_model.encode(content).tolist()
                    
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
                    
                    if verbose:
                        console.print(
                            f"[green]✓[/green] {chunk_file.name}: "
                            f"indexed {len(objects)} chunks"
                        )
                
                progress.update(main_task, advance=1)
                
            except Exception as e:
                failed_files.append((chunk_file.name, str(e)))
                if verbose:
                    console.print(f"[red]✗[/red] Error indexing {chunk_file.name}: {e}")
                progress.update(main_task, advance=1)
                continue
    
    console.print()
    return total_chunks, total_indexed, failed_files


def display_summary(total_chunks, total_indexed, failed_files, start_time=None):
    """Display indexing summary."""
    console.print(Panel.fit(
        "[bold cyan]Indexing Summary[/bold cyan]",
        border_style="cyan"
    ))
    
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total chunks found", str(total_chunks))
    table.add_row("Successfully indexed", str(total_indexed))
    table.add_row("Failed", str(len(failed_files)))
    
    if total_chunks > 0:
        success_rate = (total_indexed / total_chunks) * 100
        table.add_row("Success rate", f"{success_rate:.1f}%")
    
    console.print(table)
    console.print()
    
    if failed_files:
        console.print("[yellow]Failed files:[/yellow]")
        for filename, error in failed_files:
            console.print(f"  [red]✗[/red] {filename}: {error}")
        console.print()


def verify_indexing(client):
    """Verify that documents were indexed successfully."""
    console.print("[cyan]→[/cyan] Verifying indexing...")
    
    try:
        stats = client.get_stats()
        total = stats.get('total_chunks', 0)
        
        if total > 0:
            console.print(f"[green]✓[/green] Verified: {total} chunks in database")
            return True
        else:
            console.print("[yellow]⚠[/yellow] No chunks found in database")
            return False
    except Exception as e:
        console.print(f"[red]✗[/red] Verification failed: {e}")
        return False


def main():
    """Main indexing workflow."""
    args = parse_arguments()
    
    display_header()
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Connect to Weaviate
    client = connect_to_weaviate()
    if not client:
        sys.exit(1)
    
    try:
        # Setup schema
        if not setup_schema(client, delete_existing=args.delete_existing):
            sys.exit(1)
        
        # Load embedding model
        console.print("[cyan]→[/cyan] Loading embedding model...")
        client.load_embedding_model()
        console.print()
        
        # Find chunk files
        chunk_files = find_chunk_files(args.chunks_dir)
        if not chunk_files:
            sys.exit(1)
        
        # Index documents
        total_chunks, total_indexed, failed_files = index_documents(
            client, 
            chunk_files,
            verbose=args.verbose
        )
        
        # Display summary
        display_summary(total_chunks, total_indexed, failed_files)
        
        # Verify indexing
        verify_indexing(client)
        
        # Final message
        if total_indexed > 0:
            console.print(Panel.fit(
                "[bold green]✓ Indexing Complete![/bold green]\n"
                f"[dim]{total_indexed} chunks are ready for querying[/dim]",
                border_style="green"
            ))
            console.print()
            console.print("[bold]Next steps:[/bold]")
            console.print("  1. Start the API: [cyan]python api.py[/cyan]")
            console.print("  2. Visit: [cyan]http://localhost:8000/docs[/cyan]")
            console.print("  3. Or query directly: [cyan]POST /query[/cyan]")
        else:
            console.print(Panel.fit(
                "[bold yellow]⚠ No chunks were indexed[/bold yellow]\n"
                "[dim]Please check your chunk files[/dim]",
                border_style="yellow"
            ))
            sys.exit(1)
    
    finally:
        client.close()


if __name__ == "__main__":
    main()