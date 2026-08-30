import os
from dotenv import load_dotenv

load_dotenv()  # читает .env локально; на Railway просто ничего не найдёт и не помешает

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ADMIN_ID = os.environ.get("ADMIN_ID")

if not TELEGRAM_TOKEN or not GEMINI_API_KEY or not ADMIN_ID:
    raise RuntimeError(
        "Missing required environment variables. "
        "Make sure TELEGRAM_TOKEN, GEMINI_API_KEY and ADMIN_ID are set "
        "(in a local .env file, or in Railway's Variables tab)."
    )