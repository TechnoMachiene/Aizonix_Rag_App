from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx
import asyncio
import time
from typing import Optional
import uvicorn

app = FastAPI(title="n8n Chatbot API", version="1.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Your n8n webhook URL
N8N_WEBHOOK_URL = "http://54.226.128.109:5678/webhook/c66dd826-8130-4504-b5f6-4e7545821613/chat"

class ChatMessage(BaseModel):
    message: str
    sessionId: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    status: str
    timestamp: Optional[str] = None

# Mount static files (for serving the HTML page)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_frontend():
    """Serve the chat interface"""
    return FileResponse("static/index.html")

@app.post("/chat", response_model=ChatResponse)
async def chat_with_bot(message: ChatMessage):
    """
    Send a message to the n8n workflow and return the response
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Send message with sessionId to n8n for proper memory management
            payload = {
                "chatInput": message.message,
                "sessionId": message.sessionId or f"session_{int(time.time())}"
            }
            
            # Send request to n8n webhook
            response = await client.post(N8N_WEBHOOK_URL, json=payload)
            response.raise_for_status()
            
            # Parse the response from n8n chat trigger
            n8n_response = response.json()
            
            # n8n chat trigger returns the response directly
            if isinstance(n8n_response, dict):
                # Check for common response fields from LangChain chat trigger
                bot_response = (
                    n8n_response.get("output", "") or 
                    n8n_response.get("text", "") or 
                    n8n_response.get("response", "") or
                    str(n8n_response)
                )
            else:
                bot_response = str(n8n_response)
            
            return ChatResponse(
                response=bot_response,
                status="success"
            )
            
    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="Request timeout - n8n workflow took too long to respond")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"n8n workflow error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Test connection to n8n
            response = await client.get("http://54.226.128.109:5678")
            n8n_status = "online" if response.status_code == 200 else "offline"
    except:
        n8n_status = "offline"
    
    return {
        "status": "healthy",
        "n8n_status": n8n_status,
        "webhook_url": N8N_WEBHOOK_URL
    }

@app.get("/api/docs")
async def get_api_docs():
    """Get API documentation"""
    return {
        "endpoints": {
            "/chat": "POST - Send a message to the chatbot",
            "/health": "GET - Check API and n8n status",
            "/": "GET - Serve the chat interface"
        },
        "chat_payload": {
            "message": "Your message here",
            "sessionId": "optional_session_id (auto-generated if not provided)"
        }
    }

if __name__ == "__main__":
    print("Starting FastAPI server...")
    print(f"n8n webhook URL: {N8N_WEBHOOK_URL}")
    print("Visit http://localhost:8000 to use the chat interface")
    print("API docs available at http://localhost:8000/docs")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )