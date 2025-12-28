# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import the PDF extractor router
from app.api.pdf_extractor import router as pdf_extractor_router

app = FastAPI(
    title="Your API",
    description="API with PDF Table Extraction",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the PDF extractor router
app.include_router(pdf_extractor_router)

# Your other routers
# app.include_router(other_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "message": "API is running",
        "pdf_extractor_ui": "/pdf-extractor",
        "pdf_extractor_api": "/pdf-extractor/extract-tables",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)