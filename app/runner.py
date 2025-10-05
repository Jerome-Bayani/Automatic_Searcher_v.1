# app/runner.py
from __future__ import annotations

import math
from threading import Event
from typing import Protocol

from app.webclient_chatgpt import ChatGPTWeb
from app.notifications import notify  # <-- add this import


class QuestionSourceProto(Protocol):
    def iter_pending(self):
        """Yield (row_index, question_text)."""
        ...
    def write_answer(self, row: int, answer: str) -> None:  # type: ignore[override]
        ...


def run(source: QuestionSourceProto, *, stop_event: Event | None = None) -> None:
    """Process all pending questions. Honours an optional stop_event from the Telegram agent."""
    items = list(source.iter_pending())
    total = len(items)
    if not total:
        print("No pending questions.")
        return

    print(f"Loaded {total} items.")
    done = 0
    halfway_notified = False

    with ChatGPTWeb() as web:
        for row_idx, q in items:
            # allow /stop from the agent to interrupt cleanly
            if stop_event and stop_event.is_set():
                print("Stop requested. Exiting gracefully.")
                return

            print(f"\n→ Asking row {row_idx}...")

            # define the 5-minute warn callback
            def _warn(elapsed_s: float) -> None:
                mins = int(elapsed_s // 60)
                notify(f"Taking long ({mins} min)… still waiting on row {row_idx}")

            try:
                ans = web.ask_and_wait(
                    q,
                    warn_after_s=5 * 60,     # soft warn after 5 minutes
                    hard_stop_s=15 * 60,     # total cap 15 minutes
                    on_warn=_warn,
                )
            except TimeoutError:
                # Hard stop reached. Announce where we stopped and exit.
                notify(f"Stopped at {done} / {total} — no response after +10 minutes window.")
                print(f"Timeout on row {row_idx}. Stopping job at {done}/{total}.")
                return

            print(f"✓ Got answer ({len(ans)} chars). Writing to sheet...")
            source.write_answer(row_idx, ans)
            done += 1

            if not halfway_notified and done >= math.ceil(total / 2):
                print(f"Halfway • {done}/{total}")
                halfway_notified = True

    print("\nAll questions processed.")
