# app/sources_gsheet.py
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Iterable, List, Tuple

import gspread
from google.oauth2.service_account import Credentials


def _col_letter_to_index(letter: str) -> int:
    letter = (letter or "A").strip().upper()
    idx = 0
    for ch in letter:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return max(1, idx)


@dataclass
class SheetConfig:
    status_col_letter: str
    answer_col_letter: str

    @property
    def status_idx(self) -> int:
        return _col_letter_to_index(self.status_col_letter)

    @property
    def answer_idx(self) -> int:
        return _col_letter_to_index(self.answer_col_letter)


class GoogleSheetSource:
    """Reads questions from a column and can write answers / statuses on the same row."""

    def __init__(
        self,
        service_account_json: str,
        sheet_id: str,
        *,
        worksheet: str = "Sheet1",
        column_letter: str = "A",
    ) -> None:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(service_account_json, scopes=scopes)
        gc = gspread.authorize(creds)

        self._sh = gc.open_by_key(sheet_id)
        self._ws = self._sh.worksheet(worksheet)

        self._q_col_idx = _col_letter_to_index(column_letter)
        self._cfg = SheetConfig(
            status_col_letter=os.getenv("GSHEET_STATUS_COLUMN", "B"),
            answer_col_letter=os.getenv("ANSWER_COLUMN", "C"),
        )

    # --- reading -------------------------------------------------------------

    def get_conversation_title(self) -> str:
        """
        Return the text in row 1 of the questions column (e.g., A1 if column_letter='A').
        This is used to select the ChatGPT conversation by title.
        """
        try:
            v = self._ws.cell(1, self._q_col_idx).value or ""
        except Exception:
            v = ""
        return (v or "").strip()

    def iter_pending(self) -> Iterable[Tuple[int, str]]:
        """Yield (row_index, question_text) where status cell is empty."""
        questions: List[str] = self._ws.col_values(self._q_col_idx)
        statuses: List[str] = self._ws.col_values(self._cfg.status_idx)

        # normalize lengths
        max_len = max(len(questions), len(statuses))
        questions += [""] * (max_len - len(questions))
        statuses += [""] * (max_len - len(statuses))

        for i, (q, st) in enumerate(zip(questions, statuses), start=1):
            q = (q or "").strip()
            st = (st or "").strip()
            if i == 1:
                # skip header row; A1 is reserved for conversation title
                continue
            if q and not st:
                yield i, q

    # --- writing -------------------------------------------------------------

    def write_answer(self, row: int, answer: str) -> None:
        """Write answer to ANSWER_COLUMN at given row, and stamp DONE in STATUS column."""
        self._ws.update_cell(row, self._cfg.answer_idx, answer)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self._ws.update_cell(row, self._cfg.status_idx, f"DONE {stamp}")
