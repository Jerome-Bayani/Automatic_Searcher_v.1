from __future__ import annotations
import asyncio
import os
import threading
from typing import Optional

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.runner import run
from app.sources_gsheet import GoogleSheetSource
from app.config import DEFAULT_DELAY_SECONDS
from app.notifications import notify, notify_error  # uses requests (sync), very reliable

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "0"))
VM_NAME = os.getenv("VM_NAME", "vm")
GSA_JSON = os.getenv("GSA_JSON")
SHEET_ID = os.getenv("SHEET_ID")
WORKSHEET = os.getenv("WORKSHEET", "Sheet1")
COLUMN = os.getenv("COLUMN", "A")

if not (BOT_TOKEN and CHAT_ID and GSA_JSON and SHEET_ID):
    raise SystemExit("Missing BOT_TOKEN/CHAT_ID/GSA_JSON/SHEET_ID in .env")

_running: bool = False
_stop_event: Optional[threading.Event] = None
_job_task: Optional[asyncio.Task] = None

def _ok_sender(update: Update) -> bool:
    return bool(update.effective_chat and update.effective_chat.id == CHAT_ID)

async def _send(ctx: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """
    Send a message via PTB; if it times out or fails, fall back to requests-based notify().
    This keeps the agent responsive even on flaky networks.
    """
    try:
        await ctx.bot.send_message(chat_id=CHAT_ID, text=f"[{VM_NAME}] {text}")
    except Exception as e:
        # network hiccup: fall back to our synchronous notifier
        notify_error(f"{VM_NAME} agent send", e)
        notify(f"[{VM_NAME}] {text}")

def _work():
    """Runs in a thread; sends error or finished notification and clears running flag."""
    global _running
    try:
        src = GoogleSheetSource(GSA_JSON, SHEET_ID, worksheet=WORKSHEET, column_letter=COLUMN)
        run(src, stop_event=_stop_event)  # runner sends start/halfway/finish; we add an extra finish ping
        notify(f"[{VM_NAME}] Job finished")
    except Exception as e:
        notify_error(f"{VM_NAME} job", e)
    finally:
        _running = False

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _ok_sender(update):
        return
    global _running, _stop_event, _job_task
    if _running:
        await _send(ctx, "Already running.")
        return

    _running = True
    _stop_event = threading.Event()
    await _send(ctx, f"Starting job • delay={DEFAULT_DELAY_SECONDS}s")

    loop = asyncio.get_running_loop()
    _job_task = loop.create_task(asyncio.to_thread(_work))  # background; do NOT await
    await _send(ctx, "Job started.")

async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _ok_sender(update):
        return
    global _stop_event, _running
    if _running and _stop_event:
        _stop_event.set()
        await _send(ctx, "Stop requested.")
    else:
        await _send(ctx, "Already idle.")

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _ok_sender(update):
        return
    await _send(ctx, "Status: RUNNING" if _running else "Status: IDLE")

async def cmd_ping(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _ok_sender(update):
        return
    await _send(ctx, "Pong ✅")

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error or Exception("unknown error")
    notify_error(f"{VM_NAME} agent handler", err)

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_error_handler(on_error)
    print(f"Agent online for {VM_NAME}. /start /stop /status /ping")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
