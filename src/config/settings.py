from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AutoTech API"
    VERSION: str = "1.0.0"

    HOST: str = "127.0.0.1"
    PORT: int = 8000

    DATABASE_URL: str = ""
    SECRET_KEY: str = ""
    UPLOAD_DIR: str = "uploads"

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    FRONTEND_URL: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
