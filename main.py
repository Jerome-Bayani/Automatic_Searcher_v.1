# main.py
from __future__ import annotations

from app.runner import run
from app.sources_gsheet import GoogleSheetSource
# Importing from app.config guarantees `.env` is loaded (load_dotenv runs there)
from app.config import GSA_JSON, SHEET_ID, WORKSHEET, COLUMN

def main() -> None:
    # Fail fast if required vars are missing
    if not GSA_JSON or not SHEET_ID:
        raise SystemExit("Missing GSA_JSON and/or SHEET_ID in .env")

    source = GoogleSheetSource(
        GSA_JSON,
        SHEET_ID,
        worksheet=WORKSHEET,
        column_letter=COLUMN,
    )
    print(f"Using Google Sheet: {SHEET_ID} / {WORKSHEET} / column {COLUMN}")
    run(source)

if __name__ == "__main__":
    main()
