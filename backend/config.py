import os
import secrets
from enum import Enum
from typing import List, Dict, Optional
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppMode(str, Enum):
    DEVELOPMENT = "development"
    TEST = "test"
    PROTECTED = "protected"


class TenantCredentials:
    def __init__(self, key: str, tenant_id: str, role: str = "client", rate_limit_rpm: Optional[int] = None):
        self.key = key
        self.tenant_id = tenant_id
        self.role = role
        self.rate_limit_rpm = rate_limit_rpm

    def __repr__(self):
        return f"<TenantCredentials tenant_id={self.tenant_id} role={self.role}>"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_MODE: AppMode = Field(default=AppMode.DEVELOPMENT)
    USE_MOCK_LLM: bool = Field(default=True)
    LOCAL_LLM_API_BASE: str = Field(default="http://localhost:11434/v1")
    LOCAL_LLM_MODEL: str = Field(default="llama3")
    OPENAI_API_KEY: str = Field(default="")
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_REQUIRED_IN_PROTECTED: bool = Field(default=False)
    RATE_LIMIT_RPM: int = Field(default=60, ge=1, le=100000)
    MAX_BODY_SIZE_BYTES: int = Field(default=65536, ge=1024, le=10485760)
    MAX_MESSAGE_LENGTH: int = Field(default=2000, ge=1, le=50000)
    GATEWAY_TIMEOUT_SECONDS: float = Field(default=15.0, ge=0.5, le=300.0)
    CORS_ALLOWED_ORIGINS: str = Field(default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000")
    AUTH_KEY_REGISTRY: str = Field(default="")

    # Browser Session Authentication
    SESSION_COOKIE_NAME: str = Field(default="shieldproxy_session")
    SESSION_MAX_AGE_SECONDS: int = Field(default=3600, ge=60, le=86400)
    SESSION_COOKIE_SECURE: Optional[bool] = Field(default=None)

    @field_validator("CORS_ALLOWED_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, v: str) -> str:
        origins = [orig.strip() for orig in v.split(",") if orig.strip()]
        if not origins:
            return "http://localhost:5173"
        return ",".join(origins)

    @model_validator(mode="after")
    def validate_protected_mode_safety(self) -> "Settings":
        if self.APP_MODE == AppMode.PROTECTED:
            origins = self.cors_origins_list
            if "*" in origins:
                raise ValueError("Wildcard CORS origin '*' is strictly prohibited in protected mode.")
            if not self.AUTH_KEY_REGISTRY or "placeholder" in self.AUTH_KEY_REGISTRY:
                raise ValueError("Protected mode requires a non-empty, non-placeholder AUTH_KEY_REGISTRY.")
        return self

    @property
    def cors_origins_list(self) -> List[str]:
        return [orig.strip() for orig in self.CORS_ALLOWED_ORIGINS.split(",") if orig.strip()]

    @property
    def is_cookie_secure(self) -> bool:
        if self.SESSION_COOKIE_SECURE is not None:
            return self.SESSION_COOKIE_SECURE
        return self.APP_MODE == AppMode.PROTECTED

    @property
    def key_registry(self) -> Dict[str, TenantCredentials]:
        """Parses AUTH_KEY_REGISTRY format: key:tenant_id:role[:rpm],key2:tenant2:role2"""
        registry: Dict[str, TenantCredentials] = {}
        if not self.AUTH_KEY_REGISTRY.strip():
            # In all modes, unconfigured registry contains zero static keys (no hardcoded credentials)
            return registry

        for entry in self.AUTH_KEY_REGISTRY.split(","):
            parts = [p.strip() for p in entry.split(":") if p.strip()]
            if len(parts) >= 2:
                key = parts[0]
                tenant_id = parts[1]
                role = parts[2] if len(parts) >= 3 else "client"
                rpm = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else self.RATE_LIMIT_RPM
                registry[key] = TenantCredentials(key, tenant_id, role, rpm)
        return registry

    def __repr__(self):
        # Mask sensitive keys, credentials, and passwords in string representations
        return (
            f"<Settings APP_MODE={self.APP_MODE} USE_MOCK_LLM={self.USE_MOCK_LLM} "
            f"RATE_LIMIT_RPM={self.RATE_LIMIT_RPM} MAX_BODY_SIZE_BYTES={self.MAX_BODY_SIZE_BYTES}>"
        )


settings = Settings()

# Backwards compatibility module exports
APP_MODE = settings.APP_MODE
USE_MOCK_LLM = settings.USE_MOCK_LLM
LOCAL_LLM_API_BASE = settings.LOCAL_LLM_API_BASE
LOCAL_LLM_MODEL = settings.LOCAL_LLM_MODEL
OPENAI_API_KEY = settings.OPENAI_API_KEY
REDIS_URL = settings.REDIS_URL
RATE_LIMIT_RPM = settings.RATE_LIMIT_RPM