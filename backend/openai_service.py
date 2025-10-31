"""
Azure OpenAI Service integration with user-specific credentials
"""
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging
import asyncio

from azure.identity import AzureCliCredential
from openai import AsyncAzureOpenAI
import openai

logger = logging.getLogger(__name__)

class AzureOpenAIService:
    def __init__(self, settings, token_manager):
        self.settings = settings
        self.token_manager = token_manager
        self._clients: Dict[str, AsyncAzureOpenAI] = {}

    async def get_client(self, session_id: str) -> AsyncAzureOpenAI:
        """Get or create an Azure OpenAI client for a session"""
        # Check if client exists and is valid
        if session_id in self._clients:
            return self._clients[session_id]

        # Create new client with user-specific credentials
        client = await self._create_client(session_id)
        self._clients[session_id] = client
        return client

    async def _create_client(self, session_id: str) -> AsyncAzureOpenAI:
        """Create a new Azure OpenAI client for a session"""
        try:
            # Set Azure config directory to session-specific folder
            session_dir = Path(self.settings.SESSION_DIR) / session_id

            # IMPORTANT: Set the environment variable for the current process
            # so that AzureCliCredential can find the session-specific Azure CLI config
            old_azure_config = os.environ.get("AZURE_CONFIG_DIR")
            os.environ["AZURE_CONFIG_DIR"] = str(session_dir)

            try:
                # Create credential using Azure CLI with tenant ID
                # It will now use the session-specific Azure config directory
                cred = AzureCliCredential(
                    tenant_id=self.settings.TENANT_ID,
                    process_timeout=30
                )
            finally:
                # Restore original environment variable
                if old_azure_config:
                    os.environ["AZURE_CONFIG_DIR"] = old_azure_config
                elif "AZURE_CONFIG_DIR" in os.environ:
                    del os.environ["AZURE_CONFIG_DIR"]

            # Token provider function that uses the session's credentials
            async def token_provider():
                try:
                    # Ensure Azure config directory is set for token retrieval
                    old_config = os.environ.get("AZURE_CONFIG_DIR")
                    os.environ["AZURE_CONFIG_DIR"] = str(session_dir)

                    try:
                        # Get token from Azure CLI credential
                        token = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: cred.get_token("https://cognitiveservices.azure.com/.default")
                        )
                        return token.token
                    finally:
                        # Restore original environment
                        if old_config:
                            os.environ["AZURE_CONFIG_DIR"] = old_config
                        elif "AZURE_CONFIG_DIR" in os.environ:
                            del os.environ["AZURE_CONFIG_DIR"]
                except Exception as e:
                    logger.error(f"Failed to get token for OpenAI: {e}")
                    # Fallback to stored token
                    stored_token = await self.token_manager.get_token(session_id)
                    if stored_token:
                        return stored_token
                    raise

            # Create the client with async support
            client = AsyncAzureOpenAI(
                azure_endpoint=self.settings.AZURE_OPENAI_ENDPOINT,
                azure_ad_token_provider=token_provider,
                api_version=self.settings.AZURE_OPENAI_API_VERSION,
                default_headers={
                    "User-Agent": f"AzureAuthChat/1.0 Session/{session_id}"
                }
            )

            logger.info(f"Created Azure OpenAI client for session {session_id}")
            return client

        except Exception as e:
            logger.error(f"Failed to create OpenAI client for session {session_id}: {e}")
            raise

    async def get_chat_response(
        self,
        session_id: str,
        message: str,
        context: Optional[List[dict]] = None
    ) -> dict:
        """Get a chat response from Azure OpenAI"""
        try:
            client = await self.get_client(session_id)

            # Prepare messages
            messages = []

            # Add system message
            messages.append({
                "role": "system",
                "content": "You are a helpful AI assistant. Provide clear, concise, and accurate responses."
            })

            # Add context messages if provided
            if context:
                for ctx_msg in context:
                    messages.append({
                        "role": ctx_msg.get("role", "user"),
                        "content": ctx_msg.get("content", "")
                    })

            # Add user message
            messages.append({
                "role": "user",
                "content": message
            })

            # Make the API call
            response = await client.chat.completions.create(
                model=self.settings.AZURE_OPENAI_DEPLOYMENT,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                top_p=0.95,
                frequency_penalty=0,
                presence_penalty=0,
                stop=None
            )

            # Extract response
            if response.choices and len(response.choices) > 0:
                assistant_message = response.choices[0].message.content
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                } if response.usage else None

                return {
                    "message": assistant_message,
                    "timestamp": datetime.utcnow(),
                    "usage": usage,
                    "model": self.settings.AZURE_OPENAI_DEPLOYMENT
                }
            else:
                raise Exception("No response from OpenAI")

        except openai.AuthenticationError as e:
            logger.error(f"Authentication error for session {session_id}: {e}")
            # Try to refresh token
            if session_id in self._clients:
                del self._clients[session_id]
            raise Exception("Authentication failed. Please re-authenticate.")

        except openai.RateLimitError as e:
            logger.error(f"Rate limit error for session {session_id}: {e}")
            raise Exception("Rate limit exceeded. Please try again later.")

        except Exception as e:
            logger.error(f"Failed to get chat response for session {session_id}: {e}")
            raise

    async def stream_chat_response(
        self,
        session_id: str,
        message: str,
        context: Optional[List[dict]] = None
    ):
        """Stream a chat response from Azure OpenAI"""
        try:
            client = await self.get_client(session_id)

            # Prepare messages (same as get_chat_response)
            messages = []
            messages.append({
                "role": "system",
                "content": "You are a helpful AI assistant. Provide clear, concise, and accurate responses."
            })

            if context:
                for ctx_msg in context:
                    messages.append({
                        "role": ctx_msg.get("role", "user"),
                        "content": ctx_msg.get("content", "")
                    })

            messages.append({
                "role": "user",
                "content": message
            })

            # Stream the response
            stream = await client.chat.completions.create(
                model=self.settings.AZURE_OPENAI_DEPLOYMENT,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                stream=True
            )

            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content

        except Exception as e:
            logger.error(f"Failed to stream chat response for session {session_id}: {e}")
            raise

    async def get_embeddings(
        self,
        session_id: str,
        text: str,
        model: str = "text-embedding-ada-002"
    ) -> List[float]:
        """Get embeddings for text using Azure OpenAI"""
        try:
            client = await self.get_client(session_id)

            response = await client.embeddings.create(
                input=text,
                model=model
            )

            if response.data and len(response.data) > 0:
                return response.data[0].embedding
            else:
                raise Exception("No embeddings returned")

        except Exception as e:
            logger.error(f"Failed to get embeddings for session {session_id}: {e}")
            raise

    async def cleanup_client(self, session_id: str):
        """Clean up client for a session"""
        if session_id in self._clients:
            del self._clients[session_id]
            logger.info(f"Cleaned up OpenAI client for session {session_id}")

    async def validate_configuration(self) -> bool:
        """Validate Azure OpenAI configuration"""
        try:
            if not self.settings.AZURE_OPENAI_ENDPOINT:
                logger.error("Azure OpenAI endpoint not configured")
                return False

            if not self.settings.AZURE_OPENAI_DEPLOYMENT:
                logger.error("Azure OpenAI deployment not configured")
                return False

            if not self.settings.TENANT_ID:
                logger.error("Azure tenant ID not configured")
                return False

            logger.info("Azure OpenAI configuration validated successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to validate Azure OpenAI configuration: {e}")
            return False

    def get_client_status(self, session_id: str) -> dict:
        """Get status of OpenAI client for a session"""
        return {
            "has_client": session_id in self._clients,
            "endpoint": self.settings.AZURE_OPENAI_ENDPOINT,
            "deployment": self.settings.AZURE_OPENAI_DEPLOYMENT
        }
