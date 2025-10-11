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

# --- ETA model (baseline seconds per question, used with dynamic blend) ---
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

# --- Legacy window matching (not used in Playwright flow) ---
DEFAULT_WINDOW_MATCH = "ChatGPT"

# --- New: pacing/breaks & safety cooldown (all seconds; override via .env if desired) ---
# Mini break after every 15 questions
MINI_BREAK_EVERY_N = int(os.getenv("MINI_BREAK_EVERY_N", "15"))
MINI_BREAK_MIN_S   = int(os.getenv("MINI_BREAK_MIN_S", str(8 * 60)))   # 8 minutes
MINI_BREAK_MAX_S   = int(os.getenv("MINI_BREAK_MAX_S", str(14 * 60)))  # 14 minutes

# Long break after every 100 questions
LONG_BREAK_EVERY_N = int(os.getenv("LONG_BREAK_EVERY_N", "100"))
LONG_BREAK_MIN_S   = int(os.getenv("LONG_BREAK_MIN_S", str(30 * 60)))  # 30 minutes
LONG_BREAK_MAX_S   = int(os.getenv("LONG_BREAK_MAX_S", str(48 * 60)))  # 48 minutes

# Safety: if continuous runtime reaches 12h, pause for 6h then continue
MAX_CONTINUOUS_RUNTIME_S = int(os.getenv("MAX_CONTINUOUS_RUNTIME_S", str(12 * 60 * 60)))  # 12 hours
COOLDOWN_RUNTIME_S       = int(os.getenv("COOLDOWN_RUNTIME_S",       str(6 * 60 * 60)))   # 6 hours
