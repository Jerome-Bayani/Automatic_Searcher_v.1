from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import datetime as dt
import pathlib

import gspread
from google.oauth2.service_account import Credentials

from .config import (
    GSHEET_STATUS_COLUMN,
    GSHEET_CLEAR_ON_DONE,
    GSHEET_ARCHIVE_SHEET,
)

@dataclass(frozen=True)
class SheetItem:
    row: int
    text: str

class GoogleSheetSource:
    """
    Reads items from a Google Sheet:
      - Questions in column `column_letter` (default A)
      - Optional Status column marks processed rows (default B)
    After you send an item, call mark_done(item) to write back:
      - Writes 'DONE <timestamp>' to the Status column
      - Optionally clears the question cell
      - Optionally appends to an Archive worksheet
    """
    def __init__(
        self,
        creds_json: str | pathlib.Path,
        sheet_id: str,
        worksheet: str = "Sheet1",
        column_letter: str = "A",
        status_column: str = GSHEET_STATUS_COLUMN,
    ) -> None:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(str(pathlib.Path(creds_json)), scopes=scopes)
        self._gc = gspread.authorize(creds)
        self._sheet_id = sheet_id
        self._ws_name = worksheet
        self._col = column_letter.upper()
        self._status_col = status_column.upper()
        self._pending: List[SheetItem] = []

    # ---- read ----
    def get_items(self) -> List[SheetItem]:
        """Return pending items (question text + row index) where Status cell is empty."""
        sh = self._gc.open_by_key(self._sheet_id)
        ws = sh.worksheet(self._ws_name)

        values = ws.col_values(ord(self._col) - 64)  # A=1
        # Pad so indexing by row works safely later
        values = [""] + values  # 1-based

        status_vals: list[str]
        try:
            status_vals = ws.col_values(ord(self._status_col) - 64)
            status_vals = [""] + status_vals
        except Exception:
            status_vals = [""]

        items: List[SheetItem] = []
        max_row = max(len(values) - 1, len(status_vals) - 1)
        for row in range(1, max_row + 1):
            text = values[row] if row < len(values) else ""
            status = status_vals[row] if row < len(status_vals) else ""
            if text and not status:
                items.append(SheetItem(row=row, text=text))

        self._pending = items
        return items

    # ---- write-back ----
    def mark_done(self, item: SheetItem) -> None:
        """
        Mark a single row as processed:
          - Status cell: 'DONE <timestamp>'
          - Optional: clear question cell
          - Optional: append to Archive sheet as [timestamp, text, row]
        """
        sh = self._gc.open_by_key(self._sheet_id)
        ws = sh.worksheet(self._ws_name)

        ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_a1 = f"{self._status_col}{item.row}"
        question_a1 = f"{self._col}{item.row}"

        # Batch update in one request when possible
        updates = [{"range": status_a1, "values": [[f"DONE {ts}"]]}]
        if GSHEET_CLEAR_ON_DONE:
            updates.append({"range": question_a1, "values": [[""]]})

        ws.batch_update(
            [{"range": u["range"], "values": u["values"]} for u in updates],
            value_input_option="RAW",
        )

        if GSHEET_ARCHIVE_SHEET:
            try:
                arch = sh.worksheet(GSHEET_ARCHIVE_SHEET)
            except gspread.WorksheetNotFound:
                arch = sh.add_worksheet(title=GSHEET_ARCHIVE_SHEET, rows=1000, cols=3)
            arch.append_row([ts, item.text, item.row], value_input_option="RAW")
