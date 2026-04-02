from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8001

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/tovbase"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "identity_vectors"

    # Scoring weights
    score_existence_weight: float = 1.0
    score_consistency_weight: float = 1.0
    score_engagement_weight: float = 1.0
    score_cross_platform_weight: float = 1.0
    score_maturity_weight: float = 1.0

    # Similarity thresholds
    similarity_auto_link_threshold: float = 0.75
    similarity_review_threshold: float = 0.55

    # Cache TTLs (seconds)
    cache_score_ttl: int = 3600  # 1 hour
    cache_profile_ttl: int = 86400  # 24 hours
    cache_resolve_ttl: int = 86400  # 24 hours

    # Company scoring weights
    company_founder_weight: float = 1.0
    company_product_weight: float = 1.0
    company_community_weight: float = 1.0
    company_presence_weight: float = 1.0
    company_execution_weight: float = 1.0
    company_consistency_weight: float = 1.0

    # Behavioral vector
    vector_dimensions: int = 32

    # CORS
    cors_origins: str = "http://localhost:3002,http://localhost:3000"  # Comma-separated allowed origins
    cors_origin_regex: str = r"^chrome-extension://.*$"  # Regex for extension origins

    # Admin
    admin_api_key: str = "changeme"  # Set via ADMIN_API_KEY env var
    browser_profile_dir: str = "data/browser_profiles"

    # Crawling
    lightpanda_url: str = ""  # e.g., "http://localhost:9222" — leave empty to skip Lightpanda tier


settings = Settings()
