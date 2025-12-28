# app/api/pdf_extractor.py

from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, StreamingResponse
from pathlib import Path
import shutil
from datetime import datetime
from typing import Optional
import traceback
import zipfile
from io import BytesIO
import time
import psutil
# Import your extraction function
from app.core.py_pdf_stm.TableExtractor import extract_all_tables_auto

# Create router instead of app
router = APIRouter(prefix="/pdf-extractor", tags=["PDF Table Extractor"])

# Configuration
UPLOAD_FOLDER = Path("uploads")
OUTPUT_FOLDER = Path("outputs")
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB

# Create necessary directories
UPLOAD_FOLDER.mkdir(exist_ok=True)
OUTPUT_FOLDER.mkdir(exist_ok=True)

# Update the HTML_TEMPLATE in pdf_extractor.py

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Table Extractor</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            color: white;
            margin-bottom: 40px;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }

        .card {
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }

        .upload-section {
            text-align: center;
        }

        .file-input-wrapper {
            position: relative;
            display: inline-block;
            margin: 20px 0;
        }

        .file-input-label {
            display: inline-block;
            padding: 15px 30px;
            background: #667eea;
            color: white;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 500;
            transition: all 0.3s;
        }

        .file-input-label:hover {
            background: #5568d3;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }

        input[type="file"] {
            display: none;
        }

        .file-name {
            display: block;
            margin-top: 10px;
            color: #666;
            font-size: 14px;
        }

        .format-selector {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin: 20px 0;
        }
        
        .format-option {
            display: flex;
            align-items: center;
        }
        
        .format-option input[type="radio"] {
            width: 18px;
            height: 18px;
            margin-right: 8px;
            cursor: pointer;
        }
        
        .format-option label {
            cursor: pointer;
            font-size: 15px;
        }

        .checkbox-wrapper {
            display: flex;
            align-items: center;
            justify-content: center;
            margin-top: 15px;
        }

        .checkbox-wrapper input[type="checkbox"] {
            width: 20px;
            height: 20px;
            margin-right: 10px;
            cursor: pointer;
        }

        .btn {
            padding: 15px 40px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            margin: 10px 5px;
        }

        .btn-primary {
            background: #667eea;
            color: white;
        }

        .btn-primary:hover:not(:disabled) {
            background: #5568d3;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }

        .btn-secondary {
            background: #48bb78;
            color: white;
        }

        .btn-secondary:hover {
            background: #38a169;
        }

        .btn:disabled {
            background: #ccc;
            cursor: not-allowed;
        }

        .progress-section {
            display: none;
            text-align: center;
            padding: 20px;
        }

        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .results-section {
            display: none;
        }

        .summary {
            background: #f7fafc;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }

        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }

        .summary-item {
            text-align: center;
            padding: 15px;
            background: white;
            border-radius: 6px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }

        .summary-item .number {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }

        .summary-item .label {
            font-size: 0.9em;
            color: #666;
            margin-top: 5px;
        }

        .file-list {
            list-style: none;
        }

        .file-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            background: #f7fafc;
            border-radius: 6px;
            margin-bottom: 10px;
            transition: all 0.3s;
        }

        .file-item:hover {
            background: #edf2f7;
            transform: translateX(5px);
        }

        .file-name-text {
            flex: 1;
            font-weight: 500;
            color: #333;
        }

        .btn-small {
            padding: 8px 16px;
            font-size: 14px;
        }

        .error-message {
            background: #fed7d7;
            color: #c53030;
            padding: 15px;
            border-radius: 6px;
            margin-top: 15px;
            display: none;
        }

        .section-title {
            font-size: 1.3em;
            font-weight: 600;
            color: #333;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e0e0e0;
        }

        .download-all-section {
            text-align: center;
            padding: 20px;
            background: #f7fafc;
            border-radius: 8px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 PDF Table Extractor</h1>
            <p>Upload your PDF and extract tables automatically</p>
        </div>

        <div class="card upload-section" id="uploadSection">
            <h2 class="section-title">Upload PDF File</h2>
            
            <div class="file-input-wrapper">
                <label for="pdfFile" class="file-input-label">
                    📁 Choose PDF File
                </label>
                <input type="file" id="pdfFile" accept=".pdf">
                <span class="file-name" id="fileName">No file chosen</span>
            </div>

            <!-- Output Format Selection -->
            <div class="format-selector">
                <div class="format-option">
                    <input type="radio" id="formatCsv" name="outputFormat" value="csv" checked>
                    <label for="formatCsv">CSV (Comma-separated)</label>
                </div>
                <div class="format-option">
                    <input type="radio" id="formatExcel" name="outputFormat" value="excel">
                    <label for="formatExcel">Excel (with merged cells)</label>
                </div>
                <div class="format-option">
                    <input type="radio" id="formatBoth" name="outputFormat" value="both">
                    <label for="formatBoth">Both formats</label>
                </div>
            </div>

            <div class="checkbox-wrapper">
                <input type="checkbox" id="debugMode">
                <label for="debugMode">Enable debug mode (verbose output)</label>
            </div>

            <button class="btn btn-primary" id="extractBtn" disabled>
                🚀 Extract Tables
            </button>

            <div class="error-message" id="errorMessage"></div>
        </div>

        <div class="card progress-section" id="progressSection">
            <h2 class="section-title">Processing...</h2>
            <div class="spinner"></div>
            <p>Extracting tables from your PDF. This may take a few moments...</p>
        </div>

        <div class="card results-section" id="resultsSection">
            <h2 class="section-title">Extraction Results</h2>
            
            <div class="summary">
                <h3>Summary</h3>
                <div class="summary-grid">
                    <div class="summary-item">
                        <div class="number" id="totalPages">0</div>
                        <div class="label">Pages Processed</div>
                    </div>
                    <div class="summary-item">
                        <div class="number" id="totalTables">0</div>
                        <div class="label">Tables Extracted</div>
                    </div>
                    <div class="summary-item">
                        <div class="number" id="totalMerged">0</div>
                        <div class="label">Tables Merged</div>
                    </div>
                    <div class="summary-item">
                        <div class="number" id="totalSkipped">0</div>
                        <div class="label">Skipped</div>
                    </div>
                </div>
            </div>

            <div class="download-all-section">
                <h3>Download All Tables</h3>
                <p style="margin: 10px 0; color: #666;">Get all extracted tables in a single ZIP file</p>
                <button class="btn btn-secondary" id="downloadAllBtn">
                    📦 Download All as ZIP
                </button>
            </div>

            <h3 class="section-title">Individual Files</h3>
            <ul class="file-list" id="fileList"></ul>

            <div style="text-align: center; margin-top: 30px;">
                <button class="btn btn-primary" id="newExtractionBtn">
                    ➕ Extract Another PDF
                </button>
            </div>
        </div>
    </div>

    <script>
        let currentJobId = null;

        const pdfFileInput = document.getElementById('pdfFile');
        const fileNameDisplay = document.getElementById('fileName');
        const extractBtn = document.getElementById('extractBtn');

        pdfFileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                const file = e.target.files[0];
                fileNameDisplay.textContent = file.name;
                extractBtn.disabled = false;
            } else {
                fileNameDisplay.textContent = 'No file chosen';
                extractBtn.disabled = true;
            }
        });

        extractBtn.addEventListener('click', async () => {
            const file = pdfFileInput.files[0];
            if (!file) {
                showError('Please select a PDF file');
                return;
            }

            document.getElementById('uploadSection').style.display = 'none';
            document.getElementById('progressSection').style.display = 'block';

            try {
                const formData = new FormData();
                formData.append('file', file);
                
                const debug = document.getElementById('debugMode').checked;
                if (debug) formData.append('debug', 'true');
                
                // Get selected output format
                const outputFormat = document.querySelector('input[name="outputFormat"]:checked').value;
                formData.append('output_format', outputFormat);

                const response = await fetch('/pdf-extractor/extract-tables', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (response.ok && result.success) {
                    displayResults(result);
                } else {
                    throw new Error(result.error || 'Extraction failed');
                }

            } catch (error) {
                document.getElementById('progressSection').style.display = 'none';
                document.getElementById('uploadSection').style.display = 'block';
                showError('Error: ' + error.message);
            }
        });

        function displayResults(result) {
            currentJobId = result.job_id;

            document.getElementById('progressSection').style.display = 'none';
            document.getElementById('resultsSection').style.display = 'block';

            document.getElementById('totalPages').textContent = result.summary.total_pages_processed;
            document.getElementById('totalTables').textContent = result.summary.total_tables_extracted;
            document.getElementById('totalMerged').textContent = result.summary.tables_merged;
            document.getElementById('totalSkipped').textContent = result.summary.tables_skipped;

            const fileList = document.getElementById('fileList');
            fileList.innerHTML = '';

            // Display all generated files
            const allFiles = [...(result.csv_files || []), ...(result.excel_files || [])];
            allFiles.forEach(filename => {
                const li = document.createElement('li');
                li.className = 'file-item';
                const icon = filename.endsWith('.xlsx') ? '📊' : '📄';
                li.innerHTML = `
                    <span class="file-name-text">${icon} ${filename}</span>
                    <button class="btn btn-secondary btn-small" onclick="downloadFile('${filename}')">
                        ⬇️ Download
                    </button>
                `;
                fileList.appendChild(li);
            });

            document.getElementById('downloadAllBtn').onclick = () => downloadAll();
        }

        function downloadFile(filename) {
            window.location.href = `/pdf-extractor/download-file/${currentJobId}/${filename}`;
        }

        function downloadAll() {
            window.location.href = `/pdf-extractor/download-all/${currentJobId}`;
        }

        document.getElementById('newExtractionBtn').addEventListener('click', () => {
            document.getElementById('pdfFile').value = '';
            document.getElementById('fileName').textContent = 'No file chosen';
            document.getElementById('debugMode').checked = false;
            document.getElementById('formatCsv').checked = true;
            extractBtn.disabled = true;

            document.getElementById('resultsSection').style.display = 'none';
            document.getElementById('uploadSection').style.display = 'block';
            hideError();
        });

        function showError(message) {
            const errorDiv = document.getElementById('errorMessage');
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
        }

        function hideError() {
            document.getElementById('errorMessage').style.display = 'none';
        }
    </script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main HTML page"""
    return HTML_TEMPLATE


@router.post("/extract-tables")
async def extract_tables(
    file: UploadFile = File(...),
    debug: Optional[str] = Form(None),
    output_format: Optional[str] = Form('csv')  # Add this parameter
):
    """Extract tables from uploaded PDF file"""
    
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # Validate output format
    if output_format not in ['csv', 'excel', 'both']:
        raise HTTPException(status_code=400, detail="Invalid output format. Must be 'csv', 'excel', or 'both'")
    
    # Check file size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413, 
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE / (1024*1024)} MB"
        )
    
    # Generate unique output directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_filename = file.filename.rsplit('.', 1)[0]
    job_id = f"{timestamp}_{safe_filename}"
    
    output_dir = OUTPUT_FOLDER / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save uploaded file temporarily
    temp_pdf_path = UPLOAD_FOLDER / f"{job_id}.pdf"
    start_time = time.time()
    process = psutil.Process()
    mem_before = process.memory_info().rss / 1024 / 1024  # MB
    
    try:
        # Save file
        with open(temp_pdf_path, 'wb') as f:
            f.write(contents)
        
        # Extract tables with specified format
        debug_mode = debug and debug.lower() == 'true'
        results = extract_all_tables_auto(
            path=str(temp_pdf_path),
            output_directory=str(output_dir),
            debug=debug_mode,
            output_format=output_format  # Pass the format
        )
        
        # Get list of generated files
        csv_files = [f.name for f in output_dir.glob('*.csv')]
        excel_files = [f.name for f in output_dir.glob('*.xlsx')]
        
        # Prepare response
        response = {
            'success': True,
            'job_id': job_id,
            'filename': file.filename,
            'output_format': output_format,
            'summary': {
                'total_pages_processed': results['total_pages_processed'],
                'total_tables_extracted': results['total_tables'],
                'tables_merged': len(results['merged']),
                'tables_skipped': len(results['skipped']),
                'errors': len(results['errors'])
            },
            'extracted_tables': results['success'],
            'merged_tables': results['merged'],
            'skipped': results['skipped'],
            'errors': results['errors'],
            'csv_files': csv_files,
            'excel_files': excel_files,
            'output_directory': str(output_dir)
        }
        
        processing_time = time.time() - start_time
        mem_after = process.memory_info().rss / 1024 / 1024
        response['performance'] = {
            'processing_time_seconds': round(processing_time, 2),
            'memory_used_mb': round(mem_after - mem_before, 2),
            'pages_per_second': round(results['total_pages_processed'] / processing_time, 2) if processing_time > 0 else 0,
            'tables_per_second': round(results['total_tables'] / processing_time, 2) if processing_time > 0 else 0
        }
        
        print(response["performance"])
        return JSONResponse(content=response)
        
    except Exception as e:
        # Clean up on error
        if output_dir.exists():
            shutil.rmtree(output_dir, ignore_errors=True)
        
        raise HTTPException(
            status_code=500,
            detail={
                'error': str(e),
                'traceback': traceback.format_exc() 
            }
        )
        
    finally:
        # Clean up temporary PDF
        if temp_pdf_path.exists():
            temp_pdf_path.unlink()


# Update the download endpoint to handle both CSV and Excel
@router.get("/download-file/{job_id}/{filename}")
async def download_file(job_id: str, filename: str):
    """Download a specific file (CSV or Excel)"""
    
    file_path = OUTPUT_FOLDER / job_id / filename
    
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File {filename} not found for job {job_id}"
        )
    
    # Determine media type based on extension
    if filename.endswith('.xlsx'):
        media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        media_type = 'text/csv'
    
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )


# Update download-all to include both formats
@router.get("/download-all/{job_id}")
async def download_all(job_id: str):
    """Download all files (CSV and/or Excel) as a ZIP"""
    
    job_dir = OUTPUT_FOLDER / job_id
    
    if not job_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )
    
    # Create ZIP in memory
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add CSV files
        for csv_file in job_dir.glob('*.csv'):
            zf.write(csv_file, arcname=csv_file.name)
        # Add Excel files
        for excel_file in job_dir.glob('*.xlsx'):
            zf.write(excel_file, arcname=excel_file.name)
    
    memory_file.seek(0)
    
    return StreamingResponse(
        memory_file,
        media_type='application/zip',
        headers={'Content-Disposition': f'attachment; filename={job_id}_tables.zip'}
    )

@router.get("/list-jobs")
async def list_jobs():
    """List all extraction jobs"""
    
    jobs = []
    
    if OUTPUT_FOLDER.exists():
        for job_dir in OUTPUT_FOLDER.iterdir():
            if job_dir.is_dir():
                csv_files = [f.name for f in job_dir.glob('*.csv')]
                jobs.append({
                    'job_id': job_dir.name,
                    'csv_count': len(csv_files),
                    'csv_files': csv_files
                })
    
    return {
        'total_jobs': len(jobs),
        'jobs': jobs
    }


@router.delete("/delete-job/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and all its files"""
    
    job_dir = OUTPUT_FOLDER / job_id
    
    if not job_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )
    
    try:
        shutil.rmtree(job_dir)
        return {'success': True, 'message': f'Job {job_id} deleted successfully'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'service': 'PDF Table Extractor'
    }