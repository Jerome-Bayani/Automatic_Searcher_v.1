# app/runner.py
from __future__ import annotations

import math
from threading import Event
from typing import Protocol

from app.webclient_chatgpt import ChatGPTWeb


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
            ans = web.ask_and_wait(q)
            print(f"✓ Got answer ({len(ans)} chars). Writing to sheet...")
            source.write_answer(row_idx, ans)
            done += 1

            if not halfway_notified and done >= math.ceil(total / 2):
                print(f"Halfway • {done}/{total}")
                halfway_notified = True

    print("\nAll questions processed.")
