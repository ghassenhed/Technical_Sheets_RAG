# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import the PDF extractor router
from app.api.inference import router as inference_router, lifespan
app = FastAPI(
    title="Your API",
    description="API with RAG",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(inference_router)

@app.get("/")
async def root():
    return {
        "message": "API is running",
        "inference_api": "/ask/query",
        "docs": "/docs"
    }


