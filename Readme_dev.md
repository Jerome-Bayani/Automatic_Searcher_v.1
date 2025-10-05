# Automatic Searcher v.1 – Developer Notes

## 🧩 Overview
This project automates ChatGPT workflows using **Playwright**, **Google Sheets**, and **Telegram control**.  
Each VM runs an independent agent (e.g., `antix-01`, `antix-02`) that connects to an existing Chrome instance via CDP and interacts with ChatGPT tabs directly.

### Main Capabilities
- Reads **questions** from a Google Sheet (one column per VM or task).  
- Sends them sequentially into ChatGPT.  
- Detects when a response is finished.  
- Saves that response back into the Google Sheet (answer column).  
- Notifies the operator (via Telegram) when jobs start, finish, or fail.  
- Can be remotely started or stopped via Telegram commands (`/start`, `/stop`, `/ping`).  

---

## 🗂 Folder Structure
Automatic Searcher v.1/
│
├─ main.py # Entry point (runs depending on config)
│
├─ .env # Environment variables (API keys, Sheet IDs, etc.)
│
├─ app/
│ ├─ runner.py # Controls job flow, timing, error handling
│ ├─ notifications.py # Telegram message sender (replaced Pushbullet)
│ ├─ agent_telegram.py # Telegram command bot (handles /start, /stop, etc.)
│ ├─ sources_gsheet.py # Reads/writes data from Google Sheets
│ ├─ webclient_chatgpt.py # Playwright connector to Chrome (CDP)
│ ├─ monitor_chatgpt.py # Detects generation state & logs output
│ ├─ config.py # Shared configuration (delays, sheet info, etc.)
│ ├─ init.py # marks folder as Python package
│
├─ artifacts/ # Logs & saved JSON answers
│ └─ chatgpt_answers.jsonl
│
└─ requirements.txt # Dependencies for pip install

yaml
Copy code

---

## ⚙️ Environment Variables (.env)
GSA_JSON=service-account.json
SHEET_ID=your_google_sheet_id
WORKSHEET=Sheet1
COLUMN=A
ANSWER_COLUMN=C
TELEGRAM_BOT_TOKEN=xxxxx
TELEGRAM_CHAT_ID=xxxxx
VM_NAME=antix-01
CDP_URL=http://127.0.0.1:9222

yaml
Copy code

---

## 🚀 Usage
1. **Run Chrome with remote debugging**:
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222

markdown
Copy code
2. **Start the agent**:
python app/agent_telegram.py

yaml
Copy code
3. **Control via Telegram**:
- `/ping` → check status  
- `/start` → begin reading from sheet & sending  
- `/stop` → halt current session  

---

## 🧱 Notes
- Each VM can use a **different `.env`** (different `VM_NAME` + sheet ID).  
- Works headlessly — PyCharm is not needed once deployed.  
- Focus fix logic (Playwright-based) ensures the ChatGPT textbox is active before typing.  
- Responses are written to Google Sheets via the service account key.  

---

## 🩺 Troubleshooting
| Symptom | Likely Cause | Fix |
|----------|---------------|-----|
| First question skipped | Textbox not focused fast enough | Focus fix auto-retries; adjust delay in `webclient_chatgpt.py` |
| “No ChatGPT tab found” | Chrome not opened with CDP | Reopen Chrome with `--remote-debugging-port=9222` |
| No Telegram response | Bot token or chat ID invalid | Recheck `.env` |
| High CPU | Reduce polling frequency (POLL_BASE_S, POLL_JITTER_S) |
| Job hangs mid-run | Telegram `/stop` and `/start` resets cleanly |

---

## 🪄 Future Add-ons
- Support for multiple ChatGPT tabs (multi-session automation)
- Integrated dashboard or status display (web-based)
- Local SQLite logs for better recovery
- Additional “task modes” (e.g., blog rewriting, summarizing, tagging)

---

_This document helps synchronize development across environments and acts as your quick “map” of how 