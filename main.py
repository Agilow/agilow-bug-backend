from dotenv import load_dotenv
try:
    load_dotenv()
except Exception as e:
    print(f"⚠️ Warning: Could not load .env file: {e}")
    print("⚠️ Continuing without .env file - environment variables will be used directly")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os

# Initialize FastAPI app
app = FastAPI(
    title="Agilow Bug Backend",
    version="1.0.0",
    description="FastAPI backend for Agilow bug tracking with 2-agent system"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "🚀 Agilow Bug Backend is running!",
        "status": "success",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "agilow-bug-backend"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

