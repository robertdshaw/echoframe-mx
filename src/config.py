from pydantic_settings import BaseSettings
from typing import List, Optional, Dict, Any


class Settings(BaseSettings):
    # Database
    database_url: str = (
        "postgresql://echoframe_user:echoframe_pass@localhost:5433/echoframe"
    )

    # Redis
    redis_url: str = "redis://localhost:6379"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 4000
    openai_temperature: float = 0.7

    # Email
    smtp_host: str = "smtp.zoho.com"
    smtp_port: int = 587  # Fixed from 5433
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""
    email_to_default: str = ""

    # Application
    secret_key: str = ""
    debug: bool = True
    log_level: str = "INFO"
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000

    # Security
    cors_origins: str = "http://localhost:3000,http://localhost:8000"
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # MCP
    mcp_server_url: str = "http://localhost:3000"
    mcp_timeout: int = 30
    mcp_max_retries: int = 3

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    celery_task_serializer: str = "json"
    celery_result_serializer: str = "json"
    celery_accept_content: str = "json"
    celery_timezone: str = "UTC"

    # RSS Feed Update Intervals (minutes)
    rss_update_interval: int = 60
    risk_analysis_interval: int = 30
    email_report_interval: int = 1440
    article_cleanup_interval: int = 10080

    # AI Model Settings
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    ner_model: str = "es_core_news_sm"
    embedding_dimension: int = 384
    similarity_threshold: float = 0.85

    # Vector Database Settings
    vector_search_limit: int = 50
    vector_index_type: str = "ivfflat"

    # Content Processing
    max_article_length: int = 50000
    min_article_length: int = 100
    content_extraction_timeout: int = 30
    max_concurrent_extractions: int = 5

    # Rate Limiting
    rate_limit_per_minute: int = 60
    burst_rate_limit: int = 10

    # File Storage
    upload_dir: str = "./data/uploads"
    max_file_size: int = 10485760
    allowed_file_extensions: str = "pdf,txt,md,docx"

    # Monitoring & Health Checks
    health_check_interval: int = 60
    metrics_enabled: bool = True
    sentry_dsn: str = ""

    # External APIs
    news_api_key: str = ""

    # Agent Behavior Settings
    agent_max_iterations: int = 10
    agent_timeout: int = 300
    agent_memory_limit: int = 1000

    # Backup Settings
    backup_enabled: bool = True
    backup_interval: int = 86400
    backup_retention_days: int = 30
    backup_location: str = "./backups"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"


settings = Settings()
