from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import inventory

app = FastAPI(
    title="StockSense API",
    description="Warehousing Intelligence Platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(inventory.router, prefix="/api/inventory", tags=["inventory"])


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "StockSense API is running"}
