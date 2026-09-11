from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Tymothy"
    secret_key: str = "dev-secret-cambiar"
    database_url: str = "sqlite:///./data/app.db"
    documentos_dir: Path = BASE_DIR / "data" / "documentos"
    plantillas_dir: Path = BASE_DIR / "plantillas"
    debug: bool = False

    # IA (Groq)
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"

    # Google Sheets
    google_service_account_file: Path | None = None
    sheet_id: str | None = None
    sheet_worksheet: str = "Hoja 1"

    # Gmail
    gmail_credentials_file: Path | None = None
    gmail_token_file: Path | None = None
    gmail_sender: str | None = None
    abogado_email: str | None = None

    # Seed
    admin_username: str = "admin"
    admin_password: str = "cambiame"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
