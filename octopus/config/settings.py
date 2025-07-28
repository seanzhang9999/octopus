"""
Application settings and configuration.
"""

import logging
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # Application
    app_name: str = "Octopus"
    app_version: str = "0.1.0"
    debug: bool = True
    
    # Server
    host: str = "localhost"
    port: int = 9527
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    # Agent settings
    max_agents: int = 100
    agent_timeout: int = 300  # seconds
    
    # ANP SDK settings
    anp_sdk_enabled: bool = True
    
    # Model Provider settings
    model_provider: str = "openai"  # Currently only supports "openai"
    
    # OpenAI settings
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = None
    openai_deployment: Optional[str] = None
    openai_api_version: str = "2024-02-01"
    openai_temperature: float = 0.7
    openai_max_tokens: int = 4000

    OPENAI_MODEL_NAME: str = "gpt4.1"
    OPENAI_API_BASE_URL: str = "https://api.302.ai/v1"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings() 