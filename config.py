import os
from pathlib import Path

# Base Directory
BASE_DIR = Path(__file__).resolve().parent

# Candidate SQLite DB locations (mirroring original php candidate list)
CANDIDATE_DBS = [
    "/var/www/ats_dashboard/ats_database.sqlite",
    "/var/www/ATSRecoveryPro_backend/data/ats_database.sqlite",
    str(BASE_DIR / "ats_database.sqlite"),
]

def get_db_path() -> str:
    env_path = os.getenv("ATS_DB_PATH")
    if env_path and os.path.exists(env_path):
        return env_path
    for cand in CANDIDATE_DBS:
        if os.path.exists(cand) and os.path.getsize(cand) > 100:
            return cand
    return str(BASE_DIR / "ats_database.sqlite")

# Security Secrets
ATS_SUPER_SECRET = os.getenv("ATS_SUPER_SECRET", "ats_super_secret_key_2026")
ATS_API_BEARER = os.getenv("ATS_API_BEARER", "ats_super_secret_key_2026")

# Server Config
PORT = int(os.getenv("PORT", 8000))
HOST = os.getenv("HOST", "0.0.0.0")
