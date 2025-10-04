from __future__ import annotations
import time
import threading

from .config import (
    DEFAULT_DELAY_SECONDS,
    DEFAULT_WINDOW_MATCH,
    ALMOST_DONE_THRESHOLD,
    NOTIFY_EVERY_N,
    WARMUP_SECONDS,
    REFOCUS_BEFORE_FIRST,
    FIRST_ITEM_DOUBLE_SEND,
    FIRST_ITEM_DOUBLE_DELAY,
)
from . import actions
from .notifications import notify

class QuestionSourceProto:
    def get_items(self): ...
    def mark_done(self, item): ...

def _interruptible_sleep(total: float, stop_event: threading.Event | None) -> bool:
    """Sleep in small chunks so /stop cancels quickly. Returns True if cancelled."""
    slept = 0.0
    while slept < total:
        if stop_event and stop_event.is_set():
            return True
        chunk = min(0.5, total - slept)
        time.sleep(chunk)
        slept += chunk
    return False

def run(
    source: QuestionSourceProto,
    delay_seconds: int = DEFAULT_DELAY_SECONDS,
    stop_event: threading.Event | None = None,
) -> None:
    """Main loop: send items and write back progress to the sheet."""
    win = actions.find_window(DEFAULT_WINDOW_MATCH)
    actions.focus_window(win)

    items = source.get_items()
    if not items:
        notify("No questions found.")
        print("No questions found.")
        return

    total = len(items)
    eta_min = int((total * delay_seconds) // 60)
    notify("Automation starting", f"Loaded {total} items • ETA ~{eta_min} min")

    # Warmup to avoid first-message miss (apps sometimes need a moment to focus)
    if WARMUP_SECONDS > 0:
        time.sleep(WARMUP_SECONDS)
    if REFOCUS_BEFORE_FIRST:
        actions.focus_window(win)
        time.sleep(0.2)

    halfway_sent = False
    for i, it in enumerate(items, 1):
        if stop_event and stop_event.is_set():
            notify("Stopped", f"Stopped at item {i-1}/{total}")
            print("Stopped by request.")
            return

        # Extra safety for first item: refocus + double-send
        if i == 1 and REFOCUS_BEFORE_FIRST:
            actions.focus_window(win)
            time.sleep(0.2)

        actions.send_message(it.text)

        if i == 1 and FIRST_ITEM_DOUBLE_SEND:
            # brief pause then refocus and paste again, then proceed
            time.sleep(FIRST_ITEM_DOUBLE_DELAY)
            actions.focus_window(win)
            time.sleep(0.1)
            actions.send_message(it.text)

        # Only after sending (and possibly double-sending) do we mark as done
        try:
            source.mark_done(it)
        except Exception as e:
            print("Warning: failed to mark done:", e)

        remaining = (total - i) * delay_seconds
        if not halfway_sent and i >= total // 2:
            halfway_sent = True
            notify("Halfway there", f"~{remaining//3600}h {(remaining%3600)//60}m left")

        if ALMOST_DONE_THRESHOLD and remaining <= ALMOST_DONE_THRESHOLD and remaining > 0:
            notify("Almost done", f"~{remaining}s left")

        if NOTIFY_EVERY_N and i % NOTIFY_EVERY_N == 0:
            notify("Progress", f"{i}/{total} done")

        if _interruptible_sleep(delay_seconds, stop_event):
            notify("Stopped", f"Stopped at item {i}/{total}")
            print("Stopped during wait.")
            return

    notify("All questions sent.", f"Total: {total}")
    print("All questions sent.")
