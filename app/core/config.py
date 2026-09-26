import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "ATS Recovery Pro — FastAPI Backend"
    VERSION: str = "2.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Environment & Host
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # Security Keys
    ATS_SUPER_SECRET: str = "ats_super_secret_key_2026"
    ATS_API_BEARER: str = "ats_super_secret_key_2026"
    
    # SQLite Database Path
    ATS_DB_PATH: str = str(BASE_DIR / "ats_database.sqlite")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def get_resolved_db_path(self) -> str:
        candidate_paths = [
            self.ATS_DB_PATH,
            "/var/www/ats_dashboard/ats_database.sqlite",
            "/var/www/ATSRecoveryPro_backend/data/ats_database.sqlite",
            str(BASE_DIR / "ats_database.sqlite"),
        ]
        for cand in candidate_paths:
            if os.path.exists(cand) and os.path.getsize(cand) > 100:
                return cand
        return str(BASE_DIR / "ats_database.sqlite")

settings = Settings()
