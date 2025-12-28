import os
import json
import re
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import sys
# Add the parent directory to the path to import llm_client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.llm_client import LLMClient
    LLM_AVAILABLE = True
except ImportError:
    print("⚠ Warning: LLM client not available. Tables will not be processed.")
    LLM_AVAILABLE = False

@dataclass
class Chunk:
    content: str
    metadata: Dict[str, Any]
    chunk_id: str
    
    def to_dict(self):
        return {
            'content': self.content,
            'metadata': self.metadata,
            'chunk_id': self.chunk_id
        }


class DocumentChunker:
    """Base class for document chunking"""
    
    def __init__(self, document_type: str):
        self.document_type = document_type
        self.llm_client = LLMClient() if LLM_AVAILABLE else None
    
    def extract_product_from_filename(self, filename: str) -> str:
        """
        Extract clean product name from filename.
        Example: Qcells_Data_sheet_Q.TRON_M-G3R.12+-BFG_495-515_2025-08_Rev02_EN.md
        Output: Q.TRON_M-G3R.12+-BFG_495-515
        """
        # Remove common prefixes
        name = filename
        prefixes_to_remove = [
            'Qcells_Data_sheet_',
            'Qcells_Installation_Manual_',
            'Qcells_',
        ]
        
        for prefix in prefixes_to_remove:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
        
        # Remove file extension first
        name = re.sub(r'\.(md|pdf)$', '', name)
        
        # Remove date patterns (2025-08, 2024-08, etc.)
        name = re.sub(r'_\d{4}-\d{2}', '', name)
        
        # Remove revision patterns (Rev02, Rev04, etc.)
        name = re.sub(r'_Rev\d+', '', name)
        
        # Remove language codes at the end (_EN, _DE, _EN-1, etc.)
        name = re.sub(r'_[A-Z]{2}(-\d+)?$', '', name)
        
        # Clean up any trailing underscores or hyphens
        name = name.rstrip('_-')
        
        return name
    
    def detect_markdown_table(self, content: str) -> bool:
        """
        Detect if content contains a markdown table.
        More robust detection.
        """
        lines = content.split('\n')
        
        # Check for markdown table pattern
        # A table needs at least 3 lines: header, separator, data
        for i in range(len(lines) - 2):
            line1 = lines[i].strip()
            line2 = lines[i + 1].strip()
            line3 = lines[i + 2].strip()
            
            # Check if line has pipe characters (table columns)
            if '|' in line1 and '|' in line2 and '|' in line3:
                # Check if second line is a separator (contains dashes)
                if re.match(r'^[\s\|:-]+$', line2):
                    return True
        
        return False
    
    def process_table_with_llm(self, content: str, product: str, section_title: str) -> str:
        """
        Use LLM to convert markdown table to descriptive text.
        Preserves all data from the table.
        """
        if not self.llm_client:
            print("  ⚠ LLM not available, keeping table as-is")
            return content
        
        print(f"  🤖 Processing table with LLM in section: {section_title}")
        
        # Create prompt for LLM
        system_prompt = """You are a technical documentation expert. Your task is to convert markdown tables into clear, comprehensive descriptive text that preserves ALL information from the table.

Requirements:
1. Convert the table data into well-structured prose
2. Include EVERY piece of data from the table - do not omit any values, specifications, or details
3. Maintain technical accuracy and precision
4. Use clear, professional language
5. Organize information logically (by rows or by columns, whichever makes more sense)
6. Preserve units, ranges, and exact values
7. Keep the same level of technical detail

Do NOT:
- Omit any data or specifications
- Summarize or generalize the information
- Add information not present in the table
- Change technical terminology
"""

        user_prompt = f"""Product: {product}
Section: {section_title}

Please convert the following markdown table into comprehensive descriptive text. Make sure to include ALL data points, specifications, and values from the table:

{content}

Convert this to descriptive text while preserving every detail:"""

        try:
            # Generate description using LLM
            response = self.llm_client.generate_response(
                query=user_prompt,
                context_chunks=[],  # No context needed for this task
                system_prompt=system_prompt,
                temperature=0.3,  # Low temperature for factual accuracy
                max_tokens=2000
            )
            
            description = response.get('answer', '').strip()
            
            if description:
                print(f"  ✓ Table converted to description ({len(description)} chars)")
                return description
            else:
                print(f"  ⚠ LLM returned empty response, keeping original")
                return content
                
        except Exception as e:
            print(f"  ✗ Error processing table with LLM: {e}")
            return content
    
    def chunk(self, text: str, filename: str) -> List[Chunk]:
        """Override this method in subclasses"""
        raise NotImplementedError
    
    def detect_special_content(self, content: str) -> Dict[str, bool]:
        """Detect special content types"""
        has_table = self.detect_markdown_table(content)
        
        return {
            "has_table": has_table,
            "has_warning": any(word in content for word in ["Danger!", "Warning!", "NOTE!", "Attention!"]),
            "has_diagram": "Fig." in content or "DETAIL" in content or "diagram" in content.lower(),
            "has_specifications": any(word in content for word in ["specifications", "Specifications", "SPECIFICATIONS"])
        }
    
    def create_base_metadata(self, filename: str, section_info: Dict, content: str, product: str) -> Dict[str, Any]:
        """Create standardized metadata schema for all document types"""
        special_content = self.detect_special_content(content)
        
        return {
            # Document identification
            "document_type": self.document_type,
            "source_file": filename,
            "product": product,
            
            # Section information (standardized keys)
            "section_id": section_info.get("id"),
            "section_title": section_info.get("title"),
            "section_number": section_info.get("id"),  # Alias for compatibility
            "category": section_info.get("category"),
            
            # Content characteristics
            "has_table": special_content["has_table"],
            "has_warning": special_content["has_warning"],
            "has_diagram": special_content["has_diagram"],
            "has_specifications": special_content["has_specifications"],
            "table_processed_by_llm": False,  # Will be updated if processed
            
            # Metadata
            "char_count": len(content),
            "chunked_at": datetime.now().isoformat()
        }
    
    def find_all_headers(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Find all markdown headers in the document
        Returns list of (header_text, level, position)
        """
        headers = []
        
        # Patterns for different header styles
        patterns = [
            # ### Header or # **Header**
            (r'^(#{1,6})\s+(\*\*)?(.+?)(\*\*)?\s*$', 'markdown'),
            # **Header** on its own line
            (r'^\*\*([^*]+)\*\*\s*$', 'bold'),
        ]
        
        lines = text.split('\n')
        position = 0
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Skip empty lines
            if not stripped:
                position += len(line) + 1
                continue
            
            # Try markdown headers first (# ## ###)
            markdown_match = re.match(r'^(#{1,6})\s+(\*\*)?(.+?)(\*\*)?\s*$', stripped)
            if markdown_match:
                level = len(markdown_match.group(1))
                title = markdown_match.group(3).strip()
                headers.append((title, level, position, 'markdown'))
                position += len(line) + 1
                continue
            
            # Try bold headers (**Text**)
            bold_match = re.match(r'^\*\*([^*]+)\*\*\s*$', stripped)
            if bold_match:
                title = bold_match.group(1).strip()
                # Bold headers are treated as level 4
                headers.append((title, 4, position, 'bold'))
                position += len(line) + 1
                continue
            
            position += len(line) + 1
        
        return headers
    
    def categorize_section(self, title: str) -> str:
        """Automatically categorize section based on title"""
        title_lower = title.lower()
        
        # Category mapping
        categories = {
            'introduction': ['introduction', 'overview', 'about'],
            'technical_specifications': ['technical', 'specification', 'mechanical', 'electrical', 'dimension', 'property', 'properties'],
            'requirements': ['requirement', 'site', 'condition', 'prerequisite'],
            'installation': ['installation', 'mounting', 'install', 'mount', 'transport', 'setup'],
            'electrical': ['electrical', 'connection', 'wiring', 'circuit', 'voltage', 'current'],
            'safety': ['safety', 'danger', 'warning', 'grounding', 'ground'],
            'maintenance': ['maintenance', 'cleaning', 'clean', 'service', 'care'],
            'warranty': ['warranty', 'guarantee', 'performance warranty'],
            'certifications': ['certificate', 'qualification', 'standard', 'compliance'],
            'disposal': ['disposal', 'recycling', 'end of life'],
            'faults': ['fault', 'defect', 'troubleshoot', 'problem', 'issue']
        }
        
        # Check each category
        for category, keywords in categories.items():
            if any(keyword in title_lower for keyword in keywords):
                return category
        
        # Default category
        return 'general'


class InstallationManualChunker(DocumentChunker):
    """Chunker for Installation Manual documents - AUTOMATIC DETECTION"""
    
    def __init__(self):
        super().__init__("installation_manual")
    
    def extract_section_number(self, title: str) -> str:
        """Extract section number from title (e.g., '2.1' from '2.1 Technical specifications')"""
        match = re.match(r'^(\d+(?:\.\d+)*)\s+', title)
        if match:
            return match.group(1)
        
        # Try to find number anywhere in title
        match = re.search(r'\b(\d+(?:\.\d+)*)\b', title)
        if match:
            return match.group(1)
        
        return None
    
    def chunk(self, text: str, filename: str) -> List[Chunk]:
        chunks = []
        
        # Extract product from filename (clean version)
        product = self.extract_product_from_filename(filename)
        print(f"✓ Extracted product: {product}")
        
        # Find all headers automatically
        headers = self.find_all_headers(text)
        
        if not headers:
            print("⚠ No headers found - creating single chunk")
            # Fallback: create one chunk with entire document
            chunk = Chunk(
                content=text.strip(),
                metadata=self.create_base_metadata(
                    filename,
                    {"id": "full_document", "title": "Full Document", "category": "general"},
                    text,
                    product
                ),
                chunk_id=f"manual_full_{filename}"
            )
            return [chunk]
        
        print(f"✓ Found {len(headers)} headers:")
        for title, level, pos, htype in headers:
            print(f"  - Level {level}: {title[:60]}...")
        
        # Create chunks between headers
        for i, (title, level, position, htype) in enumerate(headers):
            # Find next header position
            if i + 1 < len(headers):
                next_position = headers[i + 1][2]
                content = text[position:next_position]
            else:
                content = text[position:]
            
            content = content.strip()
            
            # Skip very small chunks (likely table of contents or separators)
            if len(content) < 100:
                continue
            
            # Extract section number
            section_number = self.extract_section_number(title)
            section_id = section_number if section_number else f"section_{i+1}"
            
            # Categorize section
            category = self.categorize_section(title)
            
            section_info = {
                "id": section_id,
                "title": title,
                "category": category
            }
            
            # Create metadata
            metadata = self.create_base_metadata(filename, section_info, content, product)
            
            # Process tables with LLM if present
            if metadata.get('has_table'):
                print(f"  📊 Table detected in: {title}")
                processed_content = self.process_table_with_llm(content, product, title)
                if processed_content != content:
                    content = processed_content
                    metadata['table_processed_by_llm'] = True
            
            chunk = Chunk(
                content=content,
                metadata=metadata,
                chunk_id=f"manual_{section_id.replace('.', '_')}_{filename}"
            )
            
            chunks.append(chunk)
            print(f"  ✓ Created chunk: {section_id} - {title[:40]}... ({len(content)} chars)")
        
        return chunks


class DatasheetChunker(DocumentChunker):
    """Chunker for Datasheet documents - AUTOMATIC DETECTION"""
    
    def __init__(self):
        super().__init__("datasheet")
    
    def chunk(self, text: str, filename: str) -> List[Chunk]:
        chunks = []
        
        # Extract product from filename (clean version)
        product = self.extract_product_from_filename(filename)
        print(f"✓ Extracted product: {product}")
        
        # Find all headers automatically
        headers = self.find_all_headers(text)
        
        if not headers:
            print("⚠ No headers found - creating single chunk")
            chunk = Chunk(
                content=text.strip(),
                metadata=self.create_base_metadata(
                    filename,
                    {"id": "full_document", "title": "Full Document", "category": "general"},
                    text,
                    product
                ),
                chunk_id=f"datasheet_full_{filename}"
            )
            return [chunk]
        
        print(f"✓ Found {len(headers)} headers:")
        for title, level, pos, htype in headers:
            print(f"  - Level {level}: {title[:60]}...")
        
        # Create chunks between headers
        for i, (title, level, position, htype) in enumerate(headers):
            # Find next header position
            if i + 1 < len(headers):
                next_position = headers[i + 1][2]
                content = text[position:next_position]
            else:
                content = text[position:]
            
            content = content.strip()
            
            # Skip very small chunks
            if len(content) < 100:
                continue
            
            # Generate section ID from title
            section_id = re.sub(r'[^a-z0-9]+', '_', title.lower())[:30]
            
            # Categorize section
            category = self.categorize_section(title)
            
            section_info = {
                "id": section_id,
                "title": title,
                "category": category
            }
            
            # Create metadata
            metadata = self.create_base_metadata(filename, section_info, content, product)
            
            # Process tables with LLM if present
            if metadata.get('has_table'):
                print(f"  📊 Table detected in: {title}")
                processed_content = self.process_table_with_llm(content, product, title)
                if processed_content != content:
                    content = processed_content
                    metadata['table_processed_by_llm'] = True
            
            chunk = Chunk(
                content=content,
                metadata=metadata,
                chunk_id=f"datasheet_{section_id}_{filename}"
            )
            
            chunks.append(chunk)
            print(f"  ✓ Created chunk: {section_id} - {title[:40]}... ({len(content)} chars)")
        
        return chunks


class ChunkingPipeline:
    """Main pipeline to process documents dynamically"""
    
    def __init__(self, input_dir: str = "documents", output_dir: str = "chunked_output"):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Register chunkers for different document types
        self.chunkers = {
            "installation_manual": InstallationManualChunker(),
            "datasheet": DatasheetChunker()
        }
    
    def detect_document_type(self, text: str, filename: str) -> str:
        """Detect document type based on content"""
        text_lower = text.lower()
        
        # Check for installation manual markers
        if "installation and operation manual" in text_lower:
            return "installation_manual"
        
        # Check for datasheet markers
        if "electrical characteristics" in text_lower and "mechanical specification" in text_lower:
            return "datasheet"
        
        # Fallback: check filename
        if "manual" in filename.lower():
            return "installation_manual"
        elif "datasheet" in filename.lower() or "data_sheet" in filename.lower():
            return "datasheet"
        
        raise ValueError(f"Cannot detect document type for: {filename}")
    
    def process_file(self, filepath: Path) -> Dict[str, Any]:
        """Process a single file"""
        print(f"\n{'='*80}")
        print(f"Processing: {filepath.name}")
        print(f"{'='*80}")
        
        # Read file
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Detect document type
        doc_type = self.detect_document_type(text, filepath.name)
        print(f"✓ Detected document type: {doc_type}")
        
        # Get appropriate chunker
        chunker = self.chunkers.get(doc_type)
        if not chunker:
            raise ValueError(f"No chunker available for document type: {doc_type}")
        
        # Chunk the document
        chunks = chunker.chunk(text, filepath.stem)
        print(f"✓ Total chunks created: {len(chunks)}")
        
        # Count tables processed
        tables_processed = sum(1 for c in chunks if c.metadata.get('table_processed_by_llm'))
        if tables_processed > 0:
            print(f"✓ Tables processed by LLM: {tables_processed}")
        
        # Prepare output
        output = {
            "metadata": {
                "source_file": filepath.name,
                "document_type": doc_type,
                "total_chunks": len(chunks),
                "tables_processed": tables_processed,
                "processed_at": datetime.now().isoformat(),
                "total_characters": sum(c.metadata['char_count'] for c in chunks)
            },
            "chunks": [chunk.to_dict() for chunk in chunks]
        }
        
        # Save to JSON
        output_filename = f"{filepath.stem}_chunked.json"
        output_path = self.output_dir / output_filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Saved to: {output_path}")
        
        return output
    
    def process_directory(self):
        """Process all markdown files in input directory"""
        print(f"\n{'#'*80}")
        print(f"# CHUNKING PIPELINE - Starting")
        print(f"# Input Directory: {self.input_dir}")
        print(f"# Output Directory: {self.output_dir}")
        if LLM_AVAILABLE:
            print(f"# LLM Processing: ENABLED (tables will be converted to descriptions)")
        else:
            print(f"# LLM Processing: DISABLED (tables will be kept as markdown)")
        print(f"{'#'*80}")
        
        # Find all markdown files
        md_files = list(self.input_dir.glob("*.md"))
        
        if not md_files:
            print(f"\n⚠ No .md files found in {self.input_dir}")
            return
        
        print(f"\nFound {len(md_files)} markdown file(s)")
        
        results = []
        for filepath in md_files:
            try:
                result = self.process_file(filepath)
                results.append({
                    "file": filepath.name,
                    "status": "success",
                    "chunks": result["metadata"]["total_chunks"],
                    "tables_processed": result["metadata"]["tables_processed"]
                })
            except Exception as e:
                print(f"✗ Error processing {filepath.name}: {str(e)}")
                import traceback
                traceback.print_exc()
                results.append({
                    "file": filepath.name,
                    "status": "failed",
                    "error": str(e)
                })
        
        # Save summary
        self.save_summary(results)
        
        print(f"\n{'#'*80}")
        print(f"# PIPELINE COMPLETE")
        print(f"{'#'*80}")
        print(f"Processed: {len([r for r in results if r['status'] == 'success'])}/{len(results)} files")
        print(f"Total tables processed: {sum(r.get('tables_processed', 0) for r in results if r['status'] == 'success')}")
        print(f"Output directory: {self.output_dir}")
    
    def save_summary(self, results: List[Dict]):
        """Save processing summary"""
        summary_path = self.output_dir / "_processing_summary.json"
        
        summary = {
            "processed_at": datetime.now().isoformat(),
            "total_files": len(results),
            "successful": len([r for r in results if r['status'] == 'success']),
            "failed": len([r for r in results if r['status'] == 'failed']),
            "llm_available": LLM_AVAILABLE,
            "total_tables_processed": sum(r.get('tables_processed', 0) for r in results if r['status'] == 'success'),
            "results": results
        }
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n✓ Summary saved to: {summary_path}")


# Main execution
if __name__ == "__main__":
    # Create pipeline


    mother_directory = "/code/app/native_pdf_data/output"

    for directory in os.listdir(mother_directory):
        dir_path = os.path.join(mother_directory, directory)
        
           
        print(f"Processing folder: {directory}")

        pipeline = ChunkingPipeline(
            input_dir=dir_path,                # process files in this subfolder
            output_dir="/code/app/chuncks"     # where to store the chunks
        )
        
        pipeline.process_directory()
