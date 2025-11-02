"""
Token Manager with silent refresh capabilities
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging
from threading import Lock

logger = logging.getLogger(__name__)

class TokenManager:
    def __init__(self):
        self._tokens: Dict[str, dict] = {}
        self._lock = Lock()
        self._refresh_task = None
        self._running = False

    async def store_token(self, session_id: str, token: str, expires_at: str, refresh_token: Optional[str] = None):
        """Store token information for a session"""
        with self._lock:
            try:
                # Parse expiration time
                if isinstance(expires_at, str):
                    # First try ISO format parsing which handles timezone info
                    try:
                        # Handle ISO format with or without timezone
                        expires_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        # Handle different date formats
                        for fmt in [
                            "%Y-%m-%d %H:%M:%S.%f",
                            "%Y-%m-%d %H:%M:%S",
                            "%Y-%m-%dT%H:%M:%S.%fZ",
                            "%Y-%m-%dT%H:%M:%SZ",
                            "%Y-%m-%dT%H:%M:%S.%f",
                            "%Y-%m-%dT%H:%M:%S"
                        ]:
                            try:
                                expires_dt = datetime.strptime(expires_at, fmt)
                                break
                            except ValueError:
                                continue
                        else:
                            # If no format matches, use a default expiration
                            logger.warning(f"Could not parse expires_at '{expires_at}' for session {session_id}, using default 1 hour expiry")
                            expires_dt = datetime.utcnow() + timedelta(hours=1)
                else:
                    expires_dt = expires_at

                self._tokens[session_id] = {
                    "access_token": token.strip() if token else token,
                    "refresh_token": refresh_token.strip() if refresh_token else refresh_token,
                    "expires_at": expires_dt,
                    "last_refreshed": datetime.utcnow()
                }

                logger.info(f"Token stored for session {session_id}, expires at {expires_dt}")

            except Exception as e:
                logger.error(f"Failed to store token for session {session_id}: {e}")
                raise

    async def get_token(self, session_id: str) -> Optional[str]:
        """Get the access token for a session"""
        with self._lock:
            token_data = self._tokens.get(session_id)
            if token_data:
                return token_data.get("access_token")
            return None

    async def needs_refresh(self, session_id: str, buffer_minutes: int = 5) -> bool:
        """Check if a token needs refresh"""
        with self._lock:
            token_data = self._tokens.get(session_id)
            if not token_data:
                return True

            expires_at = token_data.get("expires_at")
            if not expires_at:
                return True

            # Check if token will expire within buffer time
            buffer_time = datetime.utcnow() + timedelta(minutes=buffer_minutes)
            return buffer_time >= expires_at

    async def remove_token(self, session_id: str):
        """Remove token for a session"""
        with self._lock:
            if session_id in self._tokens:
                del self._tokens[session_id]
                logger.info(f"Token removed for session {session_id}")

    async def start_refresh_scheduler(self, auth_service, check_interval_seconds: int = 60, buffer_minutes: int = 5):
        """Start the background token refresh scheduler"""
        self._running = True

        async def refresh_loop():
            while self._running:
                try:
                    await self._check_and_refresh_tokens(auth_service, buffer_minutes)
                except Exception as e:
                    logger.error(f"Error in refresh scheduler: {e}")

                await asyncio.sleep(check_interval_seconds)

        self._refresh_task = asyncio.create_task(refresh_loop())
        logger.info("Token refresh scheduler started")

    async def stop_refresh_scheduler(self):
        """Stop the background token refresh scheduler"""
        self._running = False
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        logger.info("Token refresh scheduler stopped")

    async def _check_and_refresh_tokens(self, auth_service, buffer_minutes: int):
        """Check all tokens and refresh those that need it"""
        sessions_to_refresh = []

        with self._lock:
            for session_id, token_data in self._tokens.items():
                expires_at = token_data.get("expires_at")
                if expires_at:
                    buffer_time = datetime.utcnow() + timedelta(minutes=buffer_minutes)
                    if buffer_time >= expires_at:
                        sessions_to_refresh.append(session_id)

        # Refresh tokens outside the lock
        for session_id in sessions_to_refresh:
            try:
                logger.info(f"Refreshing token for session {session_id}")
                await auth_service.refresh_session_token(session_id)
                logger.info(f"Token refreshed successfully for session {session_id}")
            except Exception as e:
                logger.error(f"Failed to refresh token for session {session_id}: {e}")
                # Don't remove the token yet - let the next request handle it

    def get_token_info(self, session_id: str) -> Optional[dict]:
        """Get token information for a session"""
        with self._lock:
            token_data = self._tokens.get(session_id)
            if token_data:
                return {
                    "expires_at": token_data.get("expires_at"),
                    "last_refreshed": token_data.get("last_refreshed"),
                    "has_refresh_token": bool(token_data.get("refresh_token"))
                }
            return None

    def get_all_sessions(self) -> list:
        """Get list of all sessions with tokens"""
        with self._lock:
            sessions = []
            for session_id, token_data in self._tokens.items():
                sessions.append({
                    "session_id": session_id,
                    "expires_at": token_data.get("expires_at"),
                    "last_refreshed": token_data.get("last_refreshed")
                })
            return sessions

    async def validate_token(self, session_id: str) -> bool:
        """Validate if a token is still valid"""
        with self._lock:
            token_data = self._tokens.get(session_id)
            if not token_data:
                return False

            expires_at = token_data.get("expires_at")
            if not expires_at:
                return False

            # Check if token is still valid
            return datetime.utcnow() < expires_at

    async def get_token_for_openai(self, session_id: str) -> Optional[str]:
        """Get token specifically formatted for Azure OpenAI"""
        token = await self.get_token(session_id)
        if token:
            # Azure OpenAI expects Bearer token format is handled by the SDK
            return token
        return None

    def cleanup_expired_tokens(self):
        """Remove expired tokens from memory"""
        with self._lock:
            expired_sessions = []
            for session_id, token_data in self._tokens.items():
                expires_at = token_data.get("expires_at")
                if expires_at and datetime.utcnow() > expires_at + timedelta(hours=1):
                    # Token expired more than 1 hour ago
                    expired_sessions.append(session_id)

            for session_id in expired_sessions:
                del self._tokens[session_id]
                logger.info(f"Cleaned up expired token for session {session_id}")

            if expired_sessions:
                logger.info(f"Cleaned up {len(expired_sessions)} expired tokens")