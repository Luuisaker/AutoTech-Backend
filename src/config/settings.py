from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AutoTech API"
    VERSION: str = "1.0.0"

    HOST: str = "127.0.0.1"
    PORT: int = 8000

    DATABASE_URL: str = ""
    SECRET_KEY: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
