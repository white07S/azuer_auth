"""
Session Manager for handling user sessions and data persistence
"""
import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional
import logging
import asyncio
from threading import Lock

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, session_dir: str):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._sessions_cache: Dict[str, dict] = {}
        self._lock = Lock()

    def create_session_dir(self, session_id: str) -> Path:
        """Create a directory for the session"""
        session_path = self.session_dir / session_id
        session_path.mkdir(parents=True, exist_ok=True)
        return session_path

    def get_session_path(self, session_id: str) -> Path:
        """Get the path for a session directory"""
        return self.session_dir / session_id

    def save_session(self, session_id: str, data: dict):
        """Save session data to disk and cache"""
        with self._lock:
            try:
                session_path = self.get_session_path(session_id)
                session_path.mkdir(parents=True, exist_ok=True)

                # Save to file
                session_file = session_path / "session.json"
                with open(session_file, 'w') as f:
                    json.dump(data, f, indent=2, default=str)

                # Update cache
                self._sessions_cache[session_id] = data

                logger.info(f"Session {session_id} saved successfully")

            except Exception as e:
                logger.error(f"Failed to save session {session_id}: {e}")
                raise

    def get_session(self, session_id: str) -> Optional[dict]:
        """Get session data from cache or disk"""
        with self._lock:
            # Check cache first
            if session_id in self._sessions_cache:
                return self._sessions_cache[session_id]

            # Load from disk
            try:
                session_file = self.get_session_path(session_id) / "session.json"
                if session_file.exists():
                    with open(session_file, 'r') as f:
                        data = json.load(f)

                    # Update cache
                    self._sessions_cache[session_id] = data
                    return data

            except Exception as e:
                logger.error(f"Failed to load session {session_id}: {e}")

            return None

    def delete_session(self, session_id: str):
        """Delete a session and its data"""
        with self._lock:
            try:
                # Remove from cache
                if session_id in self._sessions_cache:
                    del self._sessions_cache[session_id]

                # Remove from disk
                session_path = self.get_session_path(session_id)
                if session_path.exists():
                    shutil.rmtree(session_path)

                logger.info(f"Session {session_id} deleted")

            except Exception as e:
                logger.error(f"Failed to delete session {session_id}: {e}")

    def list_sessions(self) -> list:
        """List all active sessions"""
        sessions = []
        for session_path in self.session_dir.iterdir():
            if session_path.is_dir():
                session_file = session_path / "session.json"
                if session_file.exists():
                    try:
                        with open(session_file, 'r') as f:
                            data = json.load(f)
                            sessions.append({
                                "session_id": session_path.name,
                                "created_at": data.get("created_at"),
                                "status": data.get("status"),
                                "user_email": data.get("user_info", {}).get("email")
                            })
                    except Exception as e:
                        logger.warning(f"Could not read session {session_path.name}: {e}")

        return sessions

    def update_session_activity(self, session_id: str):
        """Update the last activity timestamp for a session"""
        session_data = self.get_session(session_id)
        if session_data:
            session_data["last_activity"] = datetime.utcnow().isoformat()
            self.save_session(session_id, session_data)

    def is_session_expired(self, session_id: str, timeout_hours: int = 24) -> bool:
        """Check if a session has expired"""
        session_data = self.get_session(session_id)
        if not session_data:
            return True

        last_activity = session_data.get("last_activity")
        if not last_activity:
            # Use created_at if no activity timestamp
            last_activity = session_data.get("created_at")

        if last_activity:
            try:
                last_time = datetime.fromisoformat(last_activity)
                if datetime.utcnow() - last_time > timedelta(hours=timeout_hours):
                    return True
            except Exception as e:
                logger.warning(f"Could not parse timestamp for session {session_id}: {e}")

        return False

    async def cleanup_expired_sessions(self, timeout_hours: int = 24):
        """Clean up expired sessions"""
        logger.info("Starting expired session cleanup")
        expired_count = 0

        for session_path in self.session_dir.iterdir():
            if session_path.is_dir():
                session_id = session_path.name
                if self.is_session_expired(session_id, timeout_hours):
                    try:
                        self.delete_session(session_id)
                        expired_count += 1
                        logger.info(f"Deleted expired session: {session_id}")
                    except Exception as e:
                        logger.error(f"Failed to delete expired session {session_id}: {e}")

        logger.info(f"Cleaned up {expired_count} expired sessions")

    async def cleanup_all_sessions(self):
        """Clean up all sessions (for shutdown)"""
        logger.info("Cleaning up all sessions")
        with self._lock:
            # Clear cache
            self._sessions_cache.clear()

            # Remove all session directories
            try:
                for session_path in self.session_dir.iterdir():
                    if session_path.is_dir():
                        shutil.rmtree(session_path)
            except Exception as e:
                logger.error(f"Error cleaning up sessions: {e}")

    def get_session_stats(self) -> dict:
        """Get statistics about sessions"""
        total_sessions = 0
        active_sessions = 0
        pending_sessions = 0
        error_sessions = 0

        for session_path in self.session_dir.iterdir():
            if session_path.is_dir():
                total_sessions += 1
                session_file = session_path / "session.json"
                if session_file.exists():
                    try:
                        with open(session_file, 'r') as f:
                            data = json.load(f)
                            status = data.get("status")
                            if status == "completed":
                                active_sessions += 1
                            elif status == "pending":
                                pending_sessions += 1
                            elif status == "error":
                                error_sessions += 1
                    except Exception:
                        pass

        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "pending_sessions": pending_sessions,
            "error_sessions": error_sessions
        }

    def store_chat_message(self, session_id: str, message: dict):
        """Store a chat message in the session history"""
        session_data = self.get_session(session_id)
        if session_data:
            if "chat_history" not in session_data:
                session_data["chat_history"] = []

            session_data["chat_history"].append({
                **message,
                "timestamp": datetime.utcnow().isoformat()
            })

            # Limit history size
            max_history = 100  # Keep last 100 messages
            if len(session_data["chat_history"]) > max_history:
                session_data["chat_history"] = session_data["chat_history"][-max_history:]

            self.save_session(session_id, session_data)

    def get_chat_history(self, session_id: str, limit: int = 50) -> list:
        """Get chat history for a session"""
        session_data = self.get_session(session_id)
        if session_data:
            history = session_data.get("chat_history", [])
            return history[-limit:] if limit else history
        return []