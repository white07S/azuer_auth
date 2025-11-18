"""
Multi-user chat application with Azure authentication and OpenAI integration
"""
import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import logging
import hashlib

from fastapi import APIRouter, FastAPI, HTTPException, Depends, Header, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from auth_service import AzureAuthService
from session_manager import SessionManager
from token_manager import TokenManager
from openai_service import AzureOpenAIService
from config import Settings

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = Settings()
session_manager = SessionManager(settings.SESSION_DIR)
token_manager = TokenManager()
auth_service = AzureAuthService(settings, session_manager, token_manager)
openai_service = AzureOpenAIService(settings, token_manager)

router = APIRouter()

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
    access_token: str

class ChatMessage(BaseModel):
    session_id: str
    message: str
    context: Optional[List[dict]] = None

class ChatResponse(BaseModel):
    message: str
    timestamp: datetime
    usage: Optional[dict] = None

class TokenData(BaseModel):
    session_id: str
    email: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    user_name: Optional[str] = None

def _parse_authorization_header(auth_header: str) -> Tuple[str, str]:
    parts = auth_header.split(" ", 1)
    if len(parts) != 2:
        return "", ""
    return parts[0], parts[1].strip()

def _extract_header_with_fallback(request: Request, header_name: str, supplied_value: Optional[str]) -> Optional[str]:
    """Return header value, allowing for proxy-added prefixes (e.g., X-Forwarded...)."""
    if supplied_value:
        return supplied_value

    target = header_name.lower()
    for name, value in request.headers.items():
        if name.lower() == target:
            return value

    for name, value in request.headers.items():
        if name.lower().endswith(target):
            return value

    return None

async def get_current_user(
    request: Request,
    x_session_id: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
    x_access_token: Optional[str] = Header(default=None)
) -> TokenData:
    """Retrieve the current user based on session ID and bearer token"""
    # Log all incoming headers for debugging
    logger.debug(f"Incoming headers: {dict(request.headers)}")

    session_id = _extract_header_with_fallback(request, "x-session-id", x_session_id)
    if not session_id:
        logger.error(f"Session ID not found. Available headers: {list(request.headers.keys())}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session header missing")

    # Try to get token from multiple sources
    # First try X-Access-Token (won't be stripped by proxies)
    token = _extract_header_with_fallback(request, "x-access-token", x_access_token)
    if token:
        logger.debug(f"Token found in X-Access-Token header (length: {len(token)})")

    # If not found, try standard Authorization header
    if not token:
        authorization_header = _extract_header_with_fallback(request, "authorization", authorization)
        if authorization_header:
            scheme, extracted_token = _parse_authorization_header(authorization_header)
            if scheme.lower() == "bearer" and extracted_token:
                token = extracted_token
                logger.debug(f"Token found in Authorization header (length: {len(token)})")

    if not token:
        logger.error(f"No access token found. Headers available: {list(request.headers.keys())}")
        logger.error(f"Looking for: 'x-access-token' or 'authorization'")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token missing")

    # Ensure token is properly trimmed
    token = token.strip()

    session_data = session_manager.get_session(session_id)
    if not session_data or session_data.get("status") != "completed":
        logger.warning(
            "Session %s not found or not completed. Status: %s",
            session_id,
            session_data.get("status") if session_data else "not found",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    user_info = session_data.get("user_info", {}) or {}

    # Prefer hashed session token when available (new scheme)
    session_token_hash = (
        session_data.get("session_token_hash")
        or user_info.get("session_token_hash")
    )

    if session_token_hash:
        header_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if header_hash != session_token_hash:
            logger.error(
                "Session token mismatch for session %s. Stored hash prefix: %s..., provided hash prefix: %s...",
                session_id,
                session_token_hash[:8],
                header_hash[:8],
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token",
            )
    else:
        # Backward compatibility: fall back to raw access token comparison
        stored_token = await token_manager.get_token(session_id)
        if not stored_token:
            logger.info(
                "Token not found in token_manager for session %s, checking session data",
                session_id,
            )
            stored_token = user_info.get("access_token")

        if not stored_token:
            logger.error("No stored token found for session %s", session_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No access token found for session",
            )

        if stored_token != token:
            logger.error(
                "Token mismatch for session %s. Stored token length: %s, provided token length: %s",
                session_id,
                len(stored_token) if stored_token else 0,
                len(token) if token else 0,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token",
            )

    return TokenData(
        session_id=session_id,
        email=user_info.get("email"),
        roles=user_info.get("roles", []),
        user_name=user_info.get("user_name"),
    )

class RoleChecker:
    """Dependency class to check if user has required roles."""

    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    async def __call__(
        self, current_user: TokenData = Depends(get_current_user)
    ) -> TokenData:
        """Check if user has any of the required roles."""
        if not any(role in current_user.roles for role in self.allowed_roles):
            logger.warning(
                "User %s with roles %s attempted to access resource requiring %s",
                current_user.email,
                current_user.roles,
                self.allowed_roles,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {', '.join(self.allowed_roles)}",
            )
        return current_user

# API Endpoints
@router.post("/api/auth/start", response_model=AuthStartResponse)
async def start_authentication(request: AuthStartRequest):
    """Start the Azure device code authentication flow"""
    try:
        result = await auth_service.start_device_code_auth(request.client_id)
        return AuthStartResponse(**result)
    except Exception as e:
        logger.error(f"Failed to start authentication: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/auth/status/{session_id}", response_model=AuthStatusResponse)
async def check_auth_status(session_id: str):
    """Check the status of an ongoing authentication"""
    try:
        status = await auth_service.check_auth_status(session_id)
        return AuthStatusResponse(**status)
    except Exception as e:
        logger.error(f"Failed to check auth status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/auth/complete", response_model=AuthCompleteResponse)
async def complete_authentication(request: AuthCompleteRequest):
    """Complete the authentication and get user info"""
    try:
        result = await auth_service.complete_auth(request.session_id)
        logger.info(f"Authentication completed for session {request.session_id}")
        logger.debug(f"Access token length: {len(result.get('access_token', ''))}")
        return AuthCompleteResponse(**result)
    except Exception as e:
        logger.error(f"Failed to complete authentication: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/auth/refresh/{session_id}")
async def refresh_token(
    session_id: str,
    current_user: TokenData = Depends(RoleChecker(["admin", "user"]))
):
    """Refresh the authentication token for a session"""
    try:
        if session_id != current_user.session_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session mismatch")

        result = await auth_service.refresh_session_token(session_id)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Failed to refresh token: {e}")
        raise HTTPException(status_code=401, detail="Failed to refresh token")

@router.post("/api/auth/logout/{session_id}")
async def logout(
    session_id: str,
    current_user: TokenData = Depends(RoleChecker(["admin", "user"]))
):
    """Logout and clean up session"""
    try:
        if session_id != current_user.session_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session mismatch")

        await auth_service.logout(session_id)
        return JSONResponse(content={"status": "success"})
    except Exception as e:
        logger.error(f"Failed to logout: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/session/{session_id}/info")
async def get_session_info(
    session_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Get session information"""
    logger.info(f"Getting session info for session_id: {session_id}")
    logger.debug(f"Current user session_id: {current_user.session_id}, roles: {current_user.roles}")

    try:
        if session_id != current_user.session_id:
            logger.error(f"Session mismatch: URL session_id={session_id}, token session_id={current_user.session_id}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session mismatch")

        session_data = session_manager.get_session(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")

        # Remove sensitive information
        safe_data = {
            "session_id": session_data.get("session_id"),
            "user_email": session_data.get("user_info", {}).get("email"),
            "user_name": session_data.get("user_info", {}).get("user_name"),
            "roles": session_data.get("user_info", {}).get("roles", []),
            "created_at": session_data.get("created_at"),
            "token_expires_at": session_data.get("token_expires_at")
        }
        return JSONResponse(content=safe_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/chat/message", response_model=ChatResponse)
async def send_chat_message(
    message: ChatMessage,
    current_user: TokenData = Depends(RoleChecker(["admin", "user"]))
):
    """Send a message to Azure OpenAI"""
    try:
        if message.session_id != current_user.session_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session mismatch")

        # Verify session
        session_data = session_manager.get_session(message.session_id)
        if not session_data:
            raise HTTPException(status_code=401, detail="Invalid session")

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

@router.get("/api/chat/history/{session_id}")
async def get_chat_history(
    session_id: str,
    limit: int = 50,
    current_user: TokenData = Depends(RoleChecker(["admin", "user"]))
):
    """Get chat history for a session"""
    try:
        if session_id != current_user.session_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session mismatch")

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

@router.delete("/api/chat/history/{session_id}")
async def clear_chat_history(
    session_id: str,
    current_user: TokenData = Depends(RoleChecker(["admin"]))
):
    """Clear chat history for a session"""
    try:
        if session_id != current_user.session_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session mismatch")

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

@router.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow()}

@router.get("/api/debug/headers")
async def debug_headers(request: Request):
    """Debug endpoint to see what headers are being received"""
    headers = dict(request.headers)
    logger.info(f"Debug headers endpoint called. Headers: {headers}")
    return {
        "headers": headers,
        "has_x_access_token": "x-access-token" in headers,
        "has_x_session_id": "x-session-id" in headers,
        "has_authorization": "authorization" in headers,
        "timestamp": datetime.utcnow()
    }

@router.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting Azure Auth Chat API")
    # Create necessary directories
    Path(settings.SESSION_DIR).mkdir(parents=True, exist_ok=True)
    logger.info("API started successfully")

@router.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Azure Auth Chat API")
    # Clean up any active sessions
    await session_manager.cleanup_all_sessions()

app = FastAPI(title="Azure Auth Chat API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-Access-Token", "X-Session-ID"],
    expose_headers=["*"],
)
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(
        "routers.past_api_router:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="debug"
    )
