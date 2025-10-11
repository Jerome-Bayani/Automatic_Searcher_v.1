# app/runner.py
from __future__ import annotations

import math
import random
import time
from threading import Event
from typing import Protocol

from app.webclient_chatgpt import ChatGPTWeb
from app.notifications import notify
from app.config import (
    EST_SECONDS_PER_QUESTION,
    MINI_BREAK_EVERY_N, MINI_BREAK_MIN_S, MINI_BREAK_MAX_S,
    LONG_BREAK_EVERY_N, LONG_BREAK_MIN_S, LONG_BREAK_MAX_S,
    MAX_CONTINUOUS_RUNTIME_S, COOLDOWN_RUNTIME_S,
)


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


def _sleep_with_checks(total_s: int, *, stop_event: Event | None) -> bool:
    """
    Sleep in small chunks so /stop can interrupt breaks.
    Returns False if a stop was requested; True if slept fully.
    """
    end = time.time() + max(0, total_s)
    while time.time() < end:
        if stop_event and stop_event.is_set():
            return False
        time.sleep(min(5.0, end - time.time()))
    return True


def _eta_remaining_seconds(done: int, total: int, accum_q_seconds: float, baseline_sec_per_q: float) -> int:
    """
    Halfway-style ETA: blended average of observed and baseline, times remaining questions.
    (Does not include planned breaks or cooldowns—matches your halfway behavior.)
    """
    if done <= 0:
        observed_avg = baseline_sec_per_q
    else:
        observed_avg = accum_q_seconds / max(1, done)
    blended_avg = (observed_avg + float(baseline_sec_per_q)) / 2.0  # 50-50
    remaining = max(0, total - done)
    return int(remaining * blended_avg)


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

            # Safety: if continuous runtime reached, enforce cooldown before next question
            elapsed_runtime = time.time() - run_start_ts
            if elapsed_runtime >= MAX_CONTINUOUS_RUNTIME_S:
                mins = _fmt_mmss(COOLDOWN_RUNTIME_S)
                notify(f"Safety cooldown: reached 12h runtime. Pausing for {mins}.")
                print(f"[safety] Pausing for {mins} after reaching {int(elapsed_runtime)}s.")
                if not _sleep_with_checks(COOLDOWN_RUNTIME_S, stop_event=stop_event):
                    print("Stop requested during cooldown. Exiting.")
                    return
                # reset start so next 12h window starts after cooldown
                run_start_ts = time.time()
                accum_q_seconds = 0.0  # reset observed pacing after long idle

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

            # Halfway Telegram ping with dynamic ETA (halfway-style)
            if (not halfway_notified) and done >= math.ceil(total / 2):
                eta_remaining_s = _eta_remaining_seconds(done, total, accum_q_seconds, float(EST_SECONDS_PER_QUESTION))
                notify(f"Halfway • {done}/{total} • ETA ~ {_fmt_mmss(eta_remaining_s)}")
                print(f"Halfway • {done}/{total} • ETA ~ {_fmt_mmss(eta_remaining_s)}")
                halfway_notified = True

            # --------------- pacing / breaks ---------------
            # Only apply breaks if more work remains
            if done < total:
                # Prefer LONG break over MINI if both would trigger (100 is multiple of 15)
                took_break = False

                # Long break (every 100)
                if LONG_BREAK_EVERY_N > 0 and (done % LONG_BREAK_EVERY_N == 0):
                    # Compute ETA like halfway (blended observed/baseline)
                    eta_remaining_s = _eta_remaining_seconds(done, total, accum_q_seconds, float(EST_SECONDS_PER_QUESTION))
                    notify(f"[100] • {done}/{total} • ETA ~ {_fmt_mmss(eta_remaining_s)}")

                    wait_s = random.randint(LONG_BREAK_MIN_S, max(LONG_BREAK_MIN_S, LONG_BREAK_MAX_S))
                    notify(f"Long break after {done} questions • waiting ~ {_fmt_mmss(wait_s)}")
                    print(f"[break] Long: sleeping {wait_s}s")
                    if not _sleep_with_checks(wait_s, stop_event=stop_event):
                        print("Stop requested during long break. Exiting.")
                        return
                    # After long break, you may reset pacing (optional). We'll reset to avoid skew.
                    accum_q_seconds = 0.0
                    took_break = True

                # Mini break (every 15) — only if long break didn't happen at the same milestone
                if (not took_break) and MINI_BREAK_EVERY_N > 0 and (done % MINI_BREAK_EVERY_N == 0):
                    # Compute ETA like halfway (blended observed/baseline)
                    eta_remaining_s = _eta_remaining_seconds(done, total, accum_q_seconds, float(EST_SECONDS_PER_QUESTION))
                    notify(f"[15] • {done}/{total} • ETA ~ {_fmt_mmss(eta_remaining_s)}")

                    wait_s = random.randint(MINI_BREAK_MIN_S, max(MINI_BREAK_MIN_S, MINI_BREAK_MAX_S))
                    notify(f"Mini break after {done} questions • waiting ~ {_fmt_mmss(wait_s)}")
                    print(f"[break] Mini: sleeping {wait_s}s")
                    if not _sleep_with_checks(wait_s, stop_event=stop_event):
                        print("Stop requested during mini break. Exiting.")
                        return
                    # Keep pacing data; mini break is short.

    total_elapsed = int(time.time() - run_start_ts)
    print("\nAll questions processed.")
    # Final completion message is sent by agent_telegram.py after run() returns.
