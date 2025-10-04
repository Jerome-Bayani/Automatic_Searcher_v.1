from __future__ import annotations
import os

from app.runner import run
from app.sources_gsheet import GoogleSheetSource


def main() -> None:
    # Required (fail fast if missing)
    gsa = os.environ["GSA_JSON"]
    sheet_id = os.environ["SHEET_ID"]

    # Optional (with defaults)
    worksheet = os.getenv("WORKSHEET", "Sheet1")
    column = os.getenv("COLUMN", "A")

    source = GoogleSheetSource(gsa, sheet_id, worksheet=worksheet, column_letter=column)
    print(f"Using Google Sheet: {sheet_id} / {worksheet} / column {column}")
    run(source)


if __name__ == "__main__":
    main()
