from __future__ import annotations
import sys
import time
from contextlib import contextmanager
from typing import Optional

import pyautogui
import pygetwindow as gw
import pyperclip

from .config import (
    DEFAULT_WINDOW_MATCH,
    USE_PASTE,
    TYPE_THRESHOLD_CHARS,
    PASTE_SETTLE_SECONDS,
)

# Choose the right modifier key for paste
_PASTE_MOD = "command" if sys.platform == "darwin" else "ctrl"


def find_window(title_substring: str = DEFAULT_WINDOW_MATCH) -> gw.Window:
    """Find a window whose title contains the substring (case-insensitive)."""
    title_substring = title_substring.lower()
    wins = [w for w in gw.getAllWindows() if title_substring in (w.title or "").lower()]
    if not wins:
        raise RuntimeError(f"Window with title containing '{title_substring}' not found.")
    # pick the first normal, visible window
    for w in wins:
        if not w.isMinimized and w.width > 0 and w.height > 0:
            return w
    return wins[0]


def focus_window(win: gw.Window) -> None:
    """Bring the window to front and click in its input area (center)."""
    try:
        win.activate()
    except Exception:
        pass
    time.sleep(PASTE_SETTLE_SECONDS)
    # Click near center to ensure focus in the text box region (adjust if needed)
    cx = win.left + max(10, win.width // 2)
    cy = win.top + max(10, int(win.height * 0.85))  # near bottom where chat boxes usually are
    pyautogui.click(cx, cy)
    time.sleep(PASTE_SETTLE_SECONDS)


@contextmanager
def _preserve_clipboard():
    """Save and restore clipboard to avoid clobbering user data."""
    try:
        old = pyperclip.paste()
    except Exception:
        old = None
    try:
        yield
    finally:
        if old is not None:
            try:
                pyperclip.copy(old)
            except Exception:
                pass


def _paste_text(text: str) -> None:
    """Paste text via clipboard and press Enter."""
    with _preserve_clipboard():
        pyperclip.copy(text)
        time.sleep(PASTE_SETTLE_SECONDS)
        pyautogui.hotkey(_PASTE_MOD, "v")
    time.sleep(PASTE_SETTLE_SECONDS)
    pyautogui.press("enter")


def _type_text(text: str) -> None:
    """Type text (fallback for short messages or when paste disabled)."""
    pyautogui.typewrite(text, interval=0.0)
    pyautogui.press("enter")


def send_message(text: str) -> None:
    """
    Send one message to the focused chat input.
    Default: clipboard paste (fast, reliable for long messages).
    """
    text = text or ""
    if USE_PASTE or len(text) >= TYPE_THRESHOLD_CHARS:
        _paste_text(text)
    else:
        _type_text(text)
