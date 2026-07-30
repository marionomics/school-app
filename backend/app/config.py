from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./school_v2.db"
    google_client_id: str = ""
    teacher_email: str = ""
    cors_origins: str = "http://localhost:5173"
    timezone: str = "America/Mexico_City"
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_endpoint: str = ""
    r2_bucket_name: str = ""

    @property
    def sqlalchemy_url(self) -> str:
        # Railway provides postgres:// URLs; SQLAlchemy+psycopg3 needs postgresql+psycopg://
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


settings = Settings()
