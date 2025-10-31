"""
Configuration settings for the Azure Auth Chat application
"""
import os
from pathlib import Path
from typing import Optional, List
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    """Application settings"""

    # Azure AD Settings
    TENANT_ID: str = Field(default="", env="AZURE_TENANT_ID")
    CLIENT_ID: Optional[str] = Field(default=None, env="AZURE_CLIENT_ID")

    # Azure OpenAI Settings
    AZURE_OPENAI_ENDPOINT: str = Field(default="", env="AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_DEPLOYMENT: str = Field(default="gpt-4", env="AZURE_OPENAI_DEPLOYMENT")
    AZURE_OPENAI_API_VERSION: str = Field(default="2025-01-01-preview", env="AZURE_OPENAI_API_VERSION")

    # Session Management
    SESSION_DIR: str = Field(default="./sessions", env="SESSION_DIR")
    # Alternative session directory if main fails (e.g., /tmp/sessions)
    ALT_SESSION_DIR: Optional[str] = Field(default=None, env="ALT_SESSION_DIR")
    SESSION_TIMEOUT_HOURS: int = Field(default=24, env="SESSION_TIMEOUT_HOURS")

    # Token Management
    TOKEN_REFRESH_BUFFER_MINUTES: int = Field(default=5, env="TOKEN_REFRESH_BUFFER_MINUTES")
    TOKEN_REFRESH_CHECK_INTERVAL_SECONDS: int = Field(default=60, env="TOKEN_REFRESH_CHECK_INTERVAL")

    # Authentication Settings
    AUTH_TIMEOUT_SECONDS: int = Field(default=300, env="AUTH_TIMEOUT_SECONDS")  # 5 minutes
    AUTH_POLL_INTERVAL_SECONDS: int = Field(default=2, env="AUTH_POLL_INTERVAL_SECONDS")

    # Role Mapping (Group IDs to Role Names)
    # Format: GROUP_ID:ROLE_NAME,GROUP_ID:ROLE_NAME
    ROLE_MAPPINGS: str = Field(default="", env="ROLE_MAPPINGS")

    # Allowed Roles (comma-separated)
    ALLOWED_ROLES: str = Field(default="", env="ALLOWED_ROLES")

    # Azure AD group IDs for role resolution
    AZURE_ADMIN_GROUP_IDS: str = Field(default="", env="AZURE_ADMIN_GROUP_IDS")
    AZURE_USER_GROUP_IDS: str = Field(default="", env="AZURE_USER_GROUP_IDS")

    # CORS Settings
    ALLOWED_ORIGINS: str = Field(default="http://localhost:3000", env="ALLOWED_ORIGINS")

    # Logging
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FILE: Optional[str] = Field(default=None, env="LOG_FILE")

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def role_mapping_dict(self) -> dict:
        """Parse role mappings from environment variable"""
        if not self.ROLE_MAPPINGS:
            return {}

        mappings = {}
        for mapping in self.ROLE_MAPPINGS.split(","):
            if ":" in mapping:
                group_id, role_name = mapping.split(":", 1)
                mappings[group_id.strip()] = role_name.strip()
        return mappings

    @property
    def allowed_roles_list(self) -> List[str]:
        """Parse allowed roles from environment variable"""
        if not self.ALLOWED_ROLES:
            return []
        return [role.strip() for role in self.ALLOWED_ROLES.split(",")]

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse allowed origins from environment variable"""
        if not self.ALLOWED_ORIGINS:
            return ["http://localhost:3000"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    @property
    def role_group_mapping(self) -> dict:
        """Return mapping of roles to Azure AD group IDs"""
        role_mapping = {
            "admin": [
                gid.strip()
                for gid in self.AZURE_ADMIN_GROUP_IDS.split(",")
                if gid.strip()
            ],
            "user": [
                gid.strip()
                for gid in self.AZURE_USER_GROUP_IDS.split(",")
                if gid.strip()
            ],
        }

        # Merge in legacy ROLE_MAPPINGS if provided
        if self.ROLE_MAPPINGS:
            for mapping in self.ROLE_MAPPINGS.split(","):
                if ":" in mapping:
                    group_id, role_name = mapping.split(":", 1)
                    role_name = role_name.strip()
                    group_id = group_id.strip()
                    if role_name not in role_mapping:
                        role_mapping[role_name] = []
                    if group_id:
                        role_mapping[role_name].append(group_id)

        # Remove empty role entries
        return {role: gids for role, gids in role_mapping.items() if gids}

    def validate_settings(self):
        """Validate required settings"""
        errors = []

        if not self.TENANT_ID:
            errors.append("AZURE_TENANT_ID is required")

        if not self.AZURE_OPENAI_ENDPOINT:
            errors.append("AZURE_OPENAI_ENDPOINT is required")

        if errors:
            raise ValueError(f"Configuration errors: {'; '.join(errors)}")

# Create a default settings instance
settings = Settings()

# Example .env file content:
"""
# Azure AD Configuration
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id  # Optional

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4
AZURE_OPENAI_API_VERSION=2025-01-01-preview

# Session Management
SESSION_DIR=./sessions
SESSION_TIMEOUT_HOURS=24

# Token Management
TOKEN_REFRESH_BUFFER_MINUTES=5
TOKEN_REFRESH_CHECK_INTERVAL_SECONDS=60

# Authentication
AUTH_TIMEOUT_SECONDS=300
AUTH_POLL_INTERVAL_SECONDS=2

# Role Mappings (Group ID to Role Name)
ROLE_MAPPINGS=group-id-1:admin,group-id-2:user,group-id-3:viewer
ALLOWED_ROLES=admin,user,viewer

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/app.log
"""
