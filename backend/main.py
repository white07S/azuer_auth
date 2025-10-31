"""
Multi-user chat application with Azure authentication and OpenAI integration
"""
import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List
import logging

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from auth_service import AzureAuthService
from session_manager import SessionManager
from token_manager import TokenManager
from openai_service import AzureOpenAIService
from config import Settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
settings = Settings()
app = FastAPI(title="Azure Auth Chat API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize managers
session_manager = SessionManager(settings.SESSION_DIR)
token_manager = TokenManager()
auth_service = AzureAuthService(settings, session_manager, token_manager)
openai_service = AzureOpenAIService(settings, token_manager)

# Connection manager for WebSockets
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: str):
        if session_id in self.active_connections:
            self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def send_message(self, message: str, session_id: str):
        if session_id in self.active_connections:
            for connection in self.active_connections[session_id]:
                await connection.send_text(message)

manager = ConnectionManager()

# Request/Response models
class AuthStartRequest(BaseModel):
    client_id: Optional[str] = None

class AuthStartResponse(BaseModel):
    session_id: str
    user_code: str
    verification_uri: str
    expires_at: datetime

class AuthStatusResponse(BaseModel):
    status: str  # pending, completed, error, timeout
    authorized: bool = False
    message: Optional[str] = None
    user_info: Optional[dict] = None

class AuthCompleteRequest(BaseModel):
    session_id: str

class AuthCompleteResponse(BaseModel):
    session_id: str
    user_info: dict
    roles: List[str]
    token_expires_at: datetime

class ChatMessage(BaseModel):
    session_id: str
    message: str
    context: Optional[List[dict]] = None

class ChatResponse(BaseModel):
    message: str
    timestamp: datetime
    usage: Optional[dict] = None

# API Endpoints
@app.post("/api/auth/start", response_model=AuthStartResponse)
async def start_authentication(request: AuthStartRequest):
    """Start the Azure device code authentication flow"""
    try:
        result = await auth_service.start_device_code_auth(request.client_id)
        return AuthStartResponse(**result)
    except Exception as e:
        logger.error(f"Failed to start authentication: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/auth/status/{session_id}", response_model=AuthStatusResponse)
async def check_auth_status(session_id: str):
    """Check the status of an ongoing authentication"""
    try:
        status = await auth_service.check_auth_status(session_id)
        return AuthStatusResponse(**status)
    except Exception as e:
        logger.error(f"Failed to check auth status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/complete", response_model=AuthCompleteResponse)
async def complete_authentication(request: AuthCompleteRequest):
    """Complete the authentication and get user info"""
    try:
        result = await auth_service.complete_auth(request.session_id)
        return AuthCompleteResponse(**result)
    except Exception as e:
        logger.error(f"Failed to complete authentication: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/refresh/{session_id}")
async def refresh_token(session_id: str):
    """Refresh the authentication token for a session"""
    try:
        result = await auth_service.refresh_session_token(session_id)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Failed to refresh token: {e}")
        raise HTTPException(status_code=401, detail="Failed to refresh token")

@app.post("/api/auth/logout/{session_id}")
async def logout(session_id: str):
    """Logout and clean up session"""
    try:
        await auth_service.logout(session_id)
        return JSONResponse(content={"status": "success"})
    except Exception as e:
        logger.error(f"Failed to logout: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/session/{session_id}/info")
async def get_session_info(session_id: str):
    """Get session information"""
    try:
        session_data = session_manager.get_session(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")

        # Remove sensitive information
        safe_data = {
            "session_id": session_data.get("session_id"),
            "user_email": session_data.get("email"),
            "user_name": session_data.get("user_name"),
            "roles": session_data.get("roles", []),
            "created_at": session_data.get("created_at"),
            "token_expires_at": session_data.get("token_expires_at")
        }
        return JSONResponse(content=safe_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat/message", response_model=ChatResponse)
async def send_chat_message(message: ChatMessage):
    """Send a message to Azure OpenAI"""
    try:
        # Verify session
        session_data = session_manager.get_session(message.session_id)
        if not session_data:
            raise HTTPException(status_code=401, detail="Invalid session")

        # Check if token needs refresh
        if await token_manager.needs_refresh(message.session_id):
            await auth_service.refresh_session_token(message.session_id)

        # Store user message in history
        session_manager.store_chat_message(message.session_id, {
            "role": "user",
            "content": message.message
        })

        # Get response from OpenAI
        response = await openai_service.get_chat_response(
            session_id=message.session_id,
            message=message.message,
            context=message.context
        )

        # Store assistant response in history
        session_manager.store_chat_message(message.session_id, {
            "role": "assistant",
            "content": response.get("message")
        })

        return ChatResponse(**response)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process chat message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat/history/{session_id}")
async def get_chat_history(session_id: str, limit: int = 50):
    """Get chat history for a session"""
    try:
        # Verify session exists
        session_data = session_manager.get_session(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")

        # Get chat history
        history = session_manager.get_chat_history(session_id, limit)
        return JSONResponse(content=history)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/chat/history/{session_id}")
async def clear_chat_history(session_id: str):
    """Clear chat history for a session"""
    try:
        # Verify session exists
        session_data = session_manager.get_session(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")

        # Clear chat history
        session_data["chat_history"] = []
        session_manager.save_session(session_id, session_data)
        return JSONResponse(content={"status": "success"})
    except Exception as e:
        logger.error(f"Failed to clear chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time chat"""
    await manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # Process the message
            if message.get("type") == "chat":
                # Verify session
                session_data = session_manager.get_session(session_id)
                if not session_data:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Invalid session"
                    }))
                    break

                # Check token refresh
                if await token_manager.needs_refresh(session_id):
                    await auth_service.refresh_session_token(session_id)

                # Store user message in history
                session_manager.store_chat_message(session_id, {
                    "role": "user",
                    "content": message.get("message")
                })

                # Get OpenAI response
                try:
                    response = await openai_service.get_chat_response(
                        session_id=session_id,
                        message=message.get("message"),
                        context=message.get("context")
                    )

                    # Store assistant response in history
                    session_manager.store_chat_message(session_id, {
                        "role": "assistant",
                        "content": response.get("message")
                    })

                    await websocket.send_text(json.dumps({
                        "type": "response",
                        "data": response
                    }))
                except Exception as e:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": str(e)
                    }))

    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, session_id)

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow()}

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting Azure Auth Chat API")
    # Create necessary directories
    Path(settings.SESSION_DIR).mkdir(parents=True, exist_ok=True)
    # Start token refresh scheduler
    asyncio.create_task(token_manager.start_refresh_scheduler(auth_service))
    logger.info("API started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Azure Auth Chat API")
    await token_manager.stop_refresh_scheduler()
    # Clean up any active sessions
    await session_manager.cleanup_all_sessions()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )