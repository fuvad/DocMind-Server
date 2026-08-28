from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from dotenv import load_dotenv
import os
from routers import users

load_dotenv()



app = FastAPI(
    title="AI Engineering API",
    description="Backend API for AI Engineering App",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(users.router)

@app.get("/")
async def root():
    return {"message": "AI Engineering App is running!"}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "1.0.0"
    }
    
@app.get("/posts")
async def get_all_posts():
    """ Get all Posts """
    try:
        result = supabase.table("posts").select("*").order("created_at", desc=True).execute()
        return result.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)