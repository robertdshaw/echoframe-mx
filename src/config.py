from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Database
    database_url: str = (
        "postgresql://echoframe_user:echoframe_pass@localhost:5432/echoframe"
    )

    # Redis
    redis_url: str = "redis://localhost:6379"

    # OpenAI
    openai_api_key: str = ""

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "noreply@echoframe.ai"

    # Application
    secret_key: str = "your_secret_key_here"
    debug: bool = True
    log_level: str = "INFO"

    # MCP
    mcp_server_url: str = "http://localhost:3000"

    # Intervals (minutes)
    rss_update_interval: int = 60
    risk_analysis_interval: int = 30
    email_report_interval: int = 1440  # 24 hours

    # AI Models
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    ner_model: str = "es_core_news_sm"

    # Risk thresholds
    risk_threshold_low: float = 0.3
    risk_threshold_medium: float = 0.6
    risk_threshold_high: float = 0.8

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"  # This allows extra environment variables


settings = Settings()
