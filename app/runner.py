# app/runner.py
from __future__ import annotations

import math
import time
from threading import Event
from typing import Protocol

from app.webclient_chatgpt import ChatGPTWeb
from app.notifications import notify
from app.config import EST_SECONDS_PER_QUESTION


class QuestionSourceProto(Protocol):
    def iter_pending(self):
        """Yield (row_index, question_text)."""
        ...
    def write_answer(self, row: int, answer: str) -> None:  # type: ignore[override]
        ...
    def get_conversation_title(self) -> str:
        ...


def _fmt_mmss(seconds: int) -> str:
    m, s = divmod(max(0, int(seconds)), 60)
    return f"{m:d}m {s:02d}s"


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

    # Track timing to compute observed average per-question duration
    run_start_ts = time.time()
    accum_q_seconds = 0.0

    with ChatGPTWeb() as web:
        # Ensure we're on the right ChatGPT conversation based on A1
        title = (source.get_conversation_title() or "").strip()
        if title:
            ok = web.ensure_conversation(title)
            if not ok:
                msg = f"Conversation titled '{title}' not found. Stopping."
                print(msg)
                notify(msg)
                return
            print(f"Using conversation: {title}")

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

            # Measure per-question duration
            q_start = time.time()
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

            q_elapsed = time.time() - q_start
            accum_q_seconds += q_elapsed

            print(f"✓ Got answer ({len(ans)} chars). Writing to sheet...")
            source.write_answer(row_idx, ans)
            done += 1

            # Halfway Telegram ping with dynamic ETA
            if (not halfway_notified) and done >= math.ceil(total / 2):
                # Observed avg so far (avoid div-by-zero; done>=1 here)
                observed_avg = accum_q_seconds / max(1, done)

                # Baseline from config (seconds per question)
                baseline_avg = float(EST_SECONDS_PER_QUESTION)

                # Blend 50/50: (observed + baseline) / 2
                blended_avg = (observed_avg + baseline_avg) / 2.0

                remaining = total - done
                eta_remaining_s = int(remaining * blended_avg)

                notify(f"Halfway • {done}/{total} • ETA ~ {_fmt_mmss(eta_remaining_s)}")
                print(f"Halfway • {done}/{total} • ETA ~ {_fmt_mmss(eta_remaining_s)}")
                halfway_notified = True

    total_elapsed = int(time.time() - run_start_ts)
    print("\nAll questions processed.")
    # Final completion message is already handled by agent_telegram.py after run() returns.
