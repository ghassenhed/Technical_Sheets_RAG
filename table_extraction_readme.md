# Table Extraction from STM32 Datasheets

High-performance pipeline for extracting tables from STM32 PDF datasheets with complex nested structures.

## Features

- **Smart Detection**: Automatic table boundary identification and title matching
- **Multi-Page Support**: Merges continuation tables across pages
- **High Accuracy**: 98.9% detection rate, 100% cell accuracy
- **Fast**: 5.3 pages/second on CPU-only

## How It Works

```
PDF → Detect Tables → Extract Titles → Parse Structure → Merge Pages → Export CSV
```

![Architecture](media/image2.png)

## Tech Stack

- **PDFPlumber**: Table detection and parsing
- **Python 3.10+**: Core language
- **Traditional parsing**: No ML/OCR needed

## Performance

| Metric | Value |
|--------|-------|
| Pages Processed | 181 |
| Tables Extracted | 95 |
| Processing Time | 33 seconds |
| Speed | 5.3 pages/sec |
| Accuracy | ~99% |

## Key Components

1. **Table Detection**: Uses PDFPlumber's TableFinder
2. **Title Extraction**: Regex pattern matching for "Table X." format
3. **Structure Parser**: Handles merged cells and nested structures
4. **Multi-Page Merger**: Combines continuation tables automatically
5. **CSV Export**: One file per table with sanitized filenames

## Why Traditional Parsing?

✅ Perfect for bordered tables in technical docs  
✅ 25x faster than ML approaches (0.2s vs 5s per page)  
✅ Simpler, more maintainable codebase  
✅ CPU-only deployment

---

**Time Spent**: ~8 hours