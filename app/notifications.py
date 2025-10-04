from __future__ import annotations
import traceback
import requests
import os

from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage" if TELEGRAM_BOT_TOKEN else None

def _send(text: str) -> bool:
    token, chat_id = TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    if not token or not chat_id:
        print("[notify] skipped: Telegram not configured")
        return False
    try:
        r = requests.post(_API, json={"chat_id": int(chat_id), "text": text}, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print("[notify] error:", e)
        return False

def notify(title: str, body: str = "") -> bool:
    text = title if not body else f"{title}\n{body}"
    ok = _send(text)
    if ok:
        print("[notify] sent:", title)
    return ok

def notify_error(context: str, err: Exception) -> None:
    tb = "".join(traceback.format_exception(type(err), err, err.__traceback__))
    # keep message short, include first lines of traceback
    lines = tb.strip().splitlines()
    head = "\n".join(lines[-6:])  # last few lines usually most relevant
    _send(f"❌ ERROR: {context}\n\n{head}")
    print(f"[notify] ERROR in {context}:\n{tb}")
