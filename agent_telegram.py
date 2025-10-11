# agent_telegram.py
from __future__ import annotations
import asyncio
import threading
import time
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.runner import run
from app.sources_gsheet import GoogleSheetSource
from app.notifications import notify, notify_error
from app.shutdown import install as install_shutdown_hook
from app.config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    DEFAULT_DELAY_SECONDS, EST_SECONDS_PER_QUESTION,
    MINI_BREAK_EVERY_N, MINI_BREAK_MIN_S, MINI_BREAK_MAX_S,
    LONG_BREAK_EVERY_N, LONG_BREAK_MIN_S, LONG_BREAK_MAX_S,
    MAX_CONTINUOUS_RUNTIME_S, COOLDOWN_RUNTIME_S,
    VM_NAME, GSA_JSON, SHEET_ID, WORKSHEET, COLUMN,
)

BOT_TOKEN = TELEGRAM_BOT_TOKEN
CHAT_ID = int(TELEGRAM_CHAT_ID or "0")

if not (BOT_TOKEN and CHAT_ID and GSA_JSON and SHEET_ID):
    raise SystemExit("Missing BOT_TOKEN/CHAT_ID/GSA_JSON/SHEET_ID in .env")

_running: bool = False
_stop_event: Optional[threading.Event] = None
_job_task: Optional[asyncio.Task] = None


def _ok_sender(update: Update) -> bool:
    return bool(update.effective_chat and update.effective_chat.id == CHAT_ID)


async def _send(ctx: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    try:
        await ctx.bot.send_message(chat_id=CHAT_ID, text=f"[{VM_NAME}] {text}")
    except Exception as e:
        notify_error(f"{VM_NAME} agent send", e)
        notify(f"[{VM_NAME}] {text}")


def _fmt_mmss(seconds: int) -> str:
    m, s = divmod(max(0, int(seconds)), 60)
    return f"{m:d}m {s:02d}s"


def _avg(a: int, b: int) -> float:
    return (float(a) + float(b)) / 2.0


def _project_eta_seconds(total_questions: int, est_seconds_per_q: int) -> int:
    if total_questions <= 0:
        return 0

    base = total_questions * int(est_seconds_per_q)

    num_mini = (total_questions - 1) // max(1, int(MINI_BREAK_EVERY_N))
    num_long = (total_questions - 1) // max(1, int(LONG_BREAK_EVERY_N))

    avg_mini = _avg(int(MINI_BREAK_MIN_S), int(MINI_BREAK_MAX_S))
    avg_long = _avg(int(LONG_BREAK_MIN_S), int(LONG_BREAK_MAX_S))
    breaks_total = int(num_mini * avg_mini + num_long * avg_long)

    duration_wo_cooldown = base + breaks_total
    num_cooldowns = duration_wo_cooldown // int(MAX_CONTINUOUS_RUNTIME_S)
    cooldown_total = int(num_cooldowns * int(COOLDOWN_RUNTIME_S))

    return int(duration_wo_cooldown + cooldown_total)


def _work():
    global _running
    start_ts = time.time()
    try:
        src = GoogleSheetSource(GSA_JSON, SHEET_ID, worksheet=WORKSHEET, column_letter=COLUMN)
        pending = list(src.iter_pending())
        total = len(pending)

        if total == 0:
            notify(f"[{VM_NAME}] No pending questions")
            _running = False
            return

        eta_sec = _project_eta_seconds(total, EST_SECONDS_PER_QUESTION)
        notify(f"[{VM_NAME}] Job started • {total} questions • ETA ~ {_fmt_mmss(eta_sec)}")

        run(src, stop_event=_stop_event)

        elapsed = int(time.time() - start_ts)
        notify(f"[{VM_NAME}] Job finished\nDuration: {_fmt_mmss(elapsed)}")

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
    _job_task = loop.create_task(asyncio.to_thread(_work))


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


def _on_process_exit() -> None:
    global _stop_event, _running
    if _running and _stop_event:
        try:
            _stop_event.set()
        except Exception:
            pass
    try:
        notify(f"[{VM_NAME}] Process exiting (terminal closed or killed)")
    except Exception:
        pass


def main() -> None:
    install_shutdown_hook(_on_process_exit)

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
