# app/config.py
from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

# --- Telegram ---
TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID: str | None = os.getenv("TELEGRAM_CHAT_ID")  # keep as string; cast when sending

# --- Sheets behavior ---
GSHEET_STATUS_COLUMN = os.getenv("GSHEET_STATUS_COLUMN", "B")
GSHEET_CLEAR_ON_DONE = os.getenv("GSHEET_CLEAR_ON_DONE", "false").lower() == "true"
GSHEET_ARCHIVE_SHEET = os.getenv("GSHEET_ARCHIVE_SHEET")
ANSWER_COLUMN = os.getenv("ANSWER_COLUMN", "C")  # where we write assistant answer

# --- Runner notifications ---
DEFAULT_DELAY_SECONDS = 30           # NOT used for Playwright flow pacing, kept for fallback
ALMOST_DONE_THRESHOLD = 60
NOTIFY_EVERY_N: int | None = None

# New: simple ETA model (seconds per question)
# You can override via .env: EST_SECONDS_PER_QUESTION=45
EST_SECONDS_PER_QUESTION = int(os.getenv("EST_SECONDS_PER_QUESTION", "45"))

# --- Playwright / Chrome CDP ---
CDP_URL = os.getenv("CDP_URL", "http://127.0.0.1:9222")  # Chrome started with --remote-debugging-port
POLL_BASE_S = float(os.getenv("POLL_BASE_S", "1.0"))
POLL_JITTER_S = float(os.getenv("POLL_JITTER_S", "0.5"))
THINK_MIN_S = float(os.getenv("THINK_MIN_S", "0.6"))
THINK_MAX_S = float(os.getenv("THINK_MAX_S", "3.2"))
FIRST_MESSAGE_GRACE_S = float(os.getenv("FIRST_MESSAGE_GRACE_S", "15.0"))  # extra settle before first send
NEXT_AFTER_FINISH_MIN_S = float(os.getenv("NEXT_AFTER_FINISH_MIN_S", "3.0"))
NEXT_AFTER_FINISH_MAX_S = float(os.getenv("NEXT_AFTER_FINISH_MAX_S", "4.0"))

# --- Window matching kept only for legacy UI mode (not used in Playwright flow) ---
DEFAULT_WINDOW_MATCH = "ChatGPT"
