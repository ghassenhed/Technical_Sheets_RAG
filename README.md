# Technical Test

This folder contains a setup for processing PDF files and running the related FastAPI services. Follow the instructions below to run the project.

---

## Optional: Automatically Extract ZIP Files

You can run the script to extract required ZIP files:

```bash
chmod +x extract.sh
./extract.sh
```

Or extract them manually if preferred.

---

## Run the Services

Build and start the Docker containers:

```bash
sudo docker-compose up --build
```

> ⚠️ Make sure to update the ports in the `.env` file to ports not currently used by Docker.

---

## Extract Tables

Access the PDF extractor and upload **cd00237391.pdf**

```
http://localhost:EXTRACT_TABLES_FASTAPI_PORT/pdf-extractor
```

---

## RAG Pipeline

### Optional: Process PDF Files

 files are already processed, you can skip this step to avoid waiting for model loading and CPU processing <br>
 <br>
 output in **app/native_pdf_data/output**

```bash
sudo docker exec -it rag python -m app.utils.extract_data
```

### Optional: Chunk Extracted Data

chunks are already stored, you can skip this 
<br>
<br>
**chunks in app/chunks**

```bash
sudo docker exec -it rag python -m app.utils.chuncker
```

### Necessary: Index Data

This step must be run to index documents:

```bash
sudo docker exec -it rag python -m app.utils.index_documents
```

---

## Ask Questions
**!! the first query will take a while because the embedding and reranker models are loading**
<br>

You can ask questions based on the processed data at:

```
http://localhost:RAG_FASTAPI_PORT/ask/askme
```
## Notes & Tips

Use sudo only if required by your Docker setup.

Adjust .env ports to avoid conflicts.

Skip optional steps if data is already processed to save time.

Keep track of output folders for further processing or verification.
