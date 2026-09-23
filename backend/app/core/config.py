import os
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parents[2]
# load_dotenv never overwrites an already exported process environment variable.
load_dotenv(_BACKEND_DIR / ".env.local", override=False)
load_dotenv(_BACKEND_DIR / ".env", override=False)

APP_ENV = os.getenv("APP_ENV", "development")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ding_invoice.db")
DINGTALK_CORP_ID = os.getenv("DINGTALK_CORP_ID", "")
DINGTALK_CLIENT_ID = os.getenv("DINGTALK_CLIENT_ID", "")
DINGTALK_CLIENT_SECRET = os.getenv("DINGTALK_CLIENT_SECRET", "")
DINGTALK_PROCESS_CODE = os.getenv("DINGTALK_PROCESS_CODE", "")
DINGTALK_SYNC_LOOKBACK_DAYS = int(os.getenv("DINGTALK_SYNC_LOOKBACK_DAYS", "30"))
DINGTALK_SYNC_SAFETY_OVERLAP_HOURS = int(os.getenv("DINGTALK_SYNC_SAFETY_OVERLAP_HOURS", "24"))
DINGTALK_ALLOWED_USER_IDS = {item.strip() for item in os.getenv("DINGTALK_ALLOWED_USER_IDS", "").split(",") if item.strip()}
SESSION_SECRET = os.getenv("SESSION_SECRET", "development-only-session-secret")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5174")
