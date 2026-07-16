from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AutoTech API"
    VERSION: str = "1.0.0"

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    DATABASE_URL: str = ""
    SECRET_KEY: str
    UPLOAD_DIR: str = "uploads"

    RESEND_API_KEY: str = ""
    RESEND_FROM: str = "AutoTech <onboarding@resend.dev>"
    FRONTEND_URL: str = "http://localhost:5173"
    CRON_API_KEY: str = ""

    BCV_API_URL: str = "https://ve.dolarapi.com/v1/dolares/bcv"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def async_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://") and "asyncpg" not in url:
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


settings = Settings()
