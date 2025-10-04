# app/webclient_chatgpt.py
from __future__ import annotations

import hashlib
import os
import random
import time
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Page, sync_playwright


CDP_URL = os.getenv("CDP_URL", "http://127.0.0.1:9222")

# Poll cadence + think-time (can be overridden in .env)
POLL_BASE_S = float(os.getenv("POLL_BASE_S", "1.0"))
POLL_JITTER_S = float(os.getenv("POLL_JITTER_S", "0.5"))
THINK_MIN_S = float(os.getenv("THINK_MIN_S", "0.6"))
THINK_MAX_S = float(os.getenv("THINK_MAX_S", "3.2"))

# Textbox selectors (we’ll try these in order)
TEXTBOX_CANDIDATES = [
    'textarea[placeholder*="Send a message"]',
    '[data-testid="composer"] textarea',
    'form textarea',
    '[contenteditable="true"][data-placeholder*="message"]',
    '[contenteditable="true"][aria-label*="message"]',
    '[contenteditable="true"][role="textbox"]',
]


def _jitter_sleep() -> None:
    time.sleep(max(0.05, POLL_BASE_S + random.uniform(-POLL_JITTER_S, POLL_JITTER_S)))


def _think() -> None:
    time.sleep(random.uniform(THINK_MIN_S, THINK_MAX_S))


def _is_chatgpt(page: Page) -> bool:
    u = (page.url or "").lower()
    return ("chat.openai.com" in u) or ("chatgpt.com" in u)


# Stealth DOM probe (robust across small UI changes)
EVAL_JS = r"""
(() => {
  const txt = n => (n && n.innerText ? n.innerText.trim() : "");
  const stopBtn = document.querySelector('[data-testid="stop-button"], button:has(svg[aria-label="Stop"])');
  const busyNode = document.querySelector('[aria-busy="true"], [data-state="loading"]');
  const stopText = Array.from(document.querySelectorAll('button')).some(b => /stop generating/i.test(b.innerText));
  const generating = !!(stopBtn || busyNode || stopText);

  const asstSel = [
    '[data-message-author-role="assistant"]',
    '[data-testid="assistant"]',
    '[data-testid*="assistant"]',
    'div.markdown'
  ];
  let lastAssistant = "";
  for (const s of asstSel) {
    const els = document.querySelectorAll(s);
    if (els.length) { lastAssistant = txt(els[els.length - 1]); if (lastAssistant) break; }
  }

  const userSel = [
    '[data-message-author-role="user"]',
    '[data-testid="user"]',
    '[data-testid*="user"]'
  ];
  let lastUser = "";
  for (const s of userSel) {
    const els = document.querySelectorAll(s);
    if (els.length) { lastUser = txt(els[els.length - 1]); if (lastUser) break; }
  }

  return { generating, lastAssistant, lastUser };
})()
"""


@dataclass
class _State:
    generating: bool
    last_assistant: str
    last_user: str


def _read_state(page: Page) -> _State:
    d = page.evaluate(EVAL_JS)
    return _State(
        generating=bool(d.get("generating", False)),
        last_assistant=str(d.get("lastAssistant", "")),
        last_user=str(d.get("lastUser", "")),
    )


class ChatGPTWeb:
    """Attach to existing Chrome (CDP) and ask ChatGPT, returning the final answer text."""

    def __init__(self, cdp_url: str = CDP_URL):
        self._cdp_url = cdp_url
        self._p = None
        self._browser = None
        self.page: Optional[Page] = None

    # ---------- connection / teardown ----------

    def __enter__(self) -> "ChatGPTWeb":
        self._p = sync_playwright().start()
        self._browser = self._p.chromium.connect_over_cdp(self._cdp_url)

        # find an open ChatGPT tab
        for ctx in self._browser.contexts:
            for pg in ctx.pages:
                if _is_chatgpt(pg):
                    self.page = pg
                    break
            if self.page:
                break
        if not self.page:
            raise RuntimeError("No ChatGPT tab found. Open a ChatGPT chat in your remote-debug Chrome.")

        # Bring to front and ensure DOM is ready before we do anything
        self.page.bring_to_front()
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self._browser:
                self._browser.close()
        finally:
            if self._p:
                self._p.stop()

    # ---------- focus helpers ----------

    def _focus_via_locators(self) -> bool:
        # 1) ARIA role (usually stable)
        try:
            tb = self.page.get_by_role("textbox").first
            tb.scroll_into_view_if_needed()
            tb.click(timeout=2000)
            return True
        except Exception:
            pass

        # 2) CSS candidates
        for sel in TEXTBOX_CANDIDATES:
            loc = self.page.locator(sel).first
            try:
                if loc.count() and loc.is_visible():
                    loc.scroll_into_view_if_needed()
                    loc.click(timeout=1500)
                    return True
            except Exception:
                continue
        return False

    def _force_focus_via_js(self) -> bool:
        js = r"""
        (() => {
          const isVisible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
          const candidates = [
            ...document.querySelectorAll('[contenteditable="true"][role="textbox"]'),
            ...document.querySelectorAll('[contenteditable="true"]'),
            ...document.querySelectorAll('textarea')
          ];
          for (const el of candidates) {
            if (!isVisible(el)) continue;
            try { el.focus({preventScroll:false}); el.click(); return true; } catch(e) {}
          }
          const composer = document.querySelector('[data-testid="composer"]') || document.body;
          const edit = composer.querySelector('[contenteditable="true"]');
          if (edit) { edit.focus(); edit.click(); return true; }
          return false;
        })()
        """
        try:
            return bool(self.page.evaluate(js))
        except Exception:
            return False

    def _ensure_textbox_focus(self) -> bool:
        """Best-effort focusing: locators → JS → Tab nudge → locators/JS again."""
        ok = self._focus_via_locators()
        if not ok:
            ok = self._force_focus_via_js()
        if not ok:
            try:
                self.page.keyboard.press("Tab", delay=50)
            except Exception:
                pass
            ok = self._focus_via_locators() or self._force_focus_via_js()
        return ok

    # ---------- typing helpers ----------

    def _paste_text_via_js(self, text: str) -> bool:
        """Write to the currently focused element (textarea or contenteditable)."""
        js = r"""
        (txt) => {
          const el = document.activeElement;
          if (!el) return false;
          try {
            if (el.tagName === 'TEXTAREA') {
              el.value = txt;
              el.dispatchEvent(new Event('input', {bubbles:true}));
              return true;
            }
            if (el.isContentEditable) {
              el.innerText = txt;
              el.dispatchEvent(new Event('input', {bubbles:true}));
              return true;
            }
          } catch (e) {}
          return false;
        }
        """
        try:
            return bool(self.page.evaluate(js, text))
        except Exception:
            return False

    # ---------- public API ----------

    def ask_and_wait(self, prompt: str) -> str:
        """Type prompt, submit, wait for generation to complete, return full assistant answer."""
        assert self.page is not None, "Not connected"

        # Make absolutely sure the textbox is focused before first send
        if not self._ensure_textbox_focus():
            raise RuntimeError("Could not focus the ChatGPT message box. Adjust selectors if this persists.")

        # Try JS paste first (instant, reliable for long texts); fall back to locator.fill/type
        if not self._paste_text_via_js(prompt):
            try:
                tb = self.page.get_by_role("textbox").first
                tb.fill(prompt)
            except Exception:
                # final fallback: type it (slower)
                self.page.keyboard.type(prompt, delay=10)

        _think()
        self.page.keyboard.press("Enter")

        prev_generating = False
        prev_fp = ""

        while True:
            s = _read_state(self.page)

            # generation just started
            if not prev_generating and s.generating:
                _think()

            # generation just finished
            if prev_generating and not s.generating:
                _think()
                full = s.last_assistant.strip()
                if full:
                    fp = hashlib.sha256(full.encode("utf-8", "ignore")).hexdigest()
                    if fp != prev_fp:
                        return full

            prev_generating = s.generating
            _jitter_sleep()
