from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


# Create FastAPI app
app = FastAPI(
    title="Six-Figure AI Engineering API",
    description="Backend API for Six-Figure AI Engineering application",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


"""
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}
"""