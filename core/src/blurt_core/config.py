from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_JWT_SECRET = "dev-secret-change-in-production"
_PROD_ENVS = {"production", "prod", "staging"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Deployment environment: "dev" (default) | "staging" | "production".
    environment: str = "dev"

    # Database
    database_url: str = "postgresql+psycopg://localhost/blurt"

    # Storage
    storage_backend: str = "local"
    audio_dir: str = "./data/audio"
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    audio_retention_days: int = 14
    max_upload_mb: int = 25

    # STT
    stt_provider: str = "mlx"
    stt_model: str = "mlx-community/whisper-small-mlx"
    groq_api_key: str = ""
    # When true, transcribe-and-translate to English (Whisper `translate` task).
    # Lets Hindi/Marathi (etc.) audio flow through the English-only pipeline.
    stt_translate: bool = False

    # LLM
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "llama3.1:8b"
    llm_api_key: str = "ollama"

    # Pipeline
    router_confidence_threshold: float = 0.7
    worker_concurrency: int = 1
    handled_kinds: str = ""  # comma-separated; empty = handle all kinds

    # Auth
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 8  # 8 hours

    # WebAuthn / passkeys
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "Blurt"
    webauthn_origin: str = "http://localhost:5200"  # the dev frontend origin

    # Frontend
    api_internal_url: str = "http://localhost:8000"

    @model_validator(mode="after")
    def _validate_secrets(self) -> "Settings":
        """Validate configuration before the app starts."""
        if not self.jwt_secret:
            raise ValueError("JWT_SECRET must be set to a non-empty value")
        if self.environment.lower() in _PROD_ENVS and self.jwt_secret == _DEV_JWT_SECRET:
            raise ValueError(
                f"JWT_SECRET must be set to a real value when ENVIRONMENT={self.environment!r}"
            )
        return self


settings = Settings()
