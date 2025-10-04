from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

# --- Telegram settings (read from .env) ---
TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID: str | None = os.getenv("TELEGRAM_CHAT_ID")  # keep as string; cast when sending

# --- App knobs ---
DEFAULT_WINDOW_MATCH = "ChatGPT"
DEFAULT_DELAY_SECONDS = 30           # seconds between questions
ALMOST_DONE_THRESHOLD = 60           # "almost done" notice when remaining <= this
NOTIFY_EVERY_N: int | None = None    # e.g., 5 to notify every 5 items; None disables

# --- Sending strategy ---
USE_PASTE = True                     # use clipboard + Ctrl/Cmd+V (recommended)
TYPE_THRESHOLD_CHARS = 120
PASTE_SETTLE_SECONDS = 0.20

# --- Run reliability tweaks ---
WARMUP_SECONDS = 1.0                 # extra focus time before sending the FIRST item
REFOCUS_BEFORE_FIRST = True          # click & refocus once more before the first send
FIRST_ITEM_DOUBLE_SEND = True        # NEW: send first item twice to overcome focus flakiness
FIRST_ITEM_DOUBLE_DELAY = 0.35       # pause between the two sends (seconds)

# --- Google Sheets write-back behavior ---
GSHEET_STATUS_COLUMN = os.getenv("GSHEET_STATUS_COLUMN", "B")
GSHEET_CLEAR_ON_DONE = os.getenv("GSHEET_CLEAR_ON_DONE", "false").lower() == "true"
GSHEET_ARCHIVE_SHEET = os.getenv("GSHEET_ARCHIVE_SHEET")  # optional: name of sheet to append to
