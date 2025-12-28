from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
from pathlib import Path
import easyocr
import numpy as np
import re

def filter_ocr_text(text: str) -> str:
    """
    Filter OCR text based on rules:
    - Skip if less than 8 words
    - Skip if numbers ratio > 25%
    - Fix "Notel" typo to "Note!"
    
    Args:
        text: OCR extracted text
    
    Returns:
        Filtered text or empty string
    """
    if not text.strip():
        return ""
    
    # Rule 1: Less than 8 words -> skip
    words = text.split()
    if len(words) < 8:
        return ""
    
    # Rule 2: Numbers ratio > 25% -> skip
    total_chars = len(text.replace(" ", ""))
    if total_chars > 0:
        digit_chars = sum(c.isdigit() for c in text)
        if (digit_chars / total_chars) > 0.25:
            return ""
    
    # Rule 3: Fix "Notel" typo
    text = text.replace("Notel", "Note!")
    
    return text

def pdf_to_markdown_ocr_inline(pdf_path: str, output_md_path: str = None, extract_images: bool = True) -> str:
    """
    Convert PDF to Markdown with optional OCR text extraction from images
    
    Args:
        pdf_path: Path to PDF file
        output_md_path: Output markdown path (optional)
        extract_images: If True, replace images with OCR text; if False, remove image references (default: True)
    
    Returns:
        Markdown text with OCR text inline (if extract_images=True) or with image references removed
    """
    print(f"📄 Converting: {pdf_path}")
    
    # Step 1: Convert with Marker
    print("⚙️ Extracting with Marker...")
    model_dict = create_model_dict()
    converter = PdfConverter(model_dict)
    text, metadata, images = text_from_rendered(converter(pdf_path))
    print(f"   Found {len(images)} images")
    
    # Step 2: OCR images and replace (only if extract_images is True)
    if extract_images and images:
        print(f"\n🔍 OCR on {len(images)} images...")
        # Initialize EasyOCR
        reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        
        ocr_results = {}
        for i, (img_name, img_data) in enumerate(images.items(), 1):
            print(f"   [{i}/{len(images)}] {img_name}...", end=" ")
            
            # OCR the image
            img_array = np.array(img_data)
            results = reader.readtext(img_array, detail=0, paragraph=True)
            ocr_text = '\n'.join(results).strip()
            
            # Apply filtering
            filtered_text = filter_ocr_text(ocr_text)
            ocr_results[img_name] = filtered_text
            
            if filtered_text:
                preview = filtered_text[:60].replace('\n', ' ')
                print(f"✓")
                print(f"      → {preview}...")
            else:
                print("✓ (filtered out)")
        
        # Step 3: Replace image references with OCR text
        print("\n📝 Replacing image references with OCR text...")
        def replace_with_ocr(match):
            img_name = match.group(2)
            ocr_text = ocr_results.get(img_name, "")
            if ocr_text:
                # Replace with OCR text only (no image)
                return f"\n{ocr_text}\n"
            else:
                # No text found, remove image reference
                return "\n"
        
        # Replace all image markdown references
        pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        text = re.sub(pattern, replace_with_ocr, text)
        
        # Clean up excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
    
    elif not extract_images and images:
        print(f"\n🗑️ Removing {len(images)} image references (extract_images=False)")
        
        # Remove all image markdown references
        pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        text = re.sub(pattern, '\n', text)
        
        # Clean up excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Step 4: Save markdown
    if output_md_path is None:
        output_md_path = str(Path(pdf_path).with_suffix('.md'))
    
    with open(output_md_path, 'w', encoding='utf-8') as f:
        f.write(text)
    
    print(f"\n✅ Done! Saved to: {output_md_path}")
    print(f"   Final text length: {len(text):,} characters\n")
    
    return text
# Usage
"""markdown = pdf_to_markdown_ocr_inline(
    "/home/ghassen/Downloads/Qcells_Data_sheet_Q.TRON_BLK_S-G3R.12+-BFG_435-450_2025-08_Rev04_EN.pdf",
    "/home/ghassen/Desktop/test.md"
)

# Preview output
print("Preview of output:")
print("="*60)
print(markdown[:1000])"""