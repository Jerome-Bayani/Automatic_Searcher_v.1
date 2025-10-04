from __future__ import annotations
import os
import asyncio
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()  # loads .env from project root

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # numeric string

async def main() -> None:
    assert TOKEN and CHAT_ID, "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env"
    bot = Bot(TOKEN)
    await bot.send_message(chat_id=int(CHAT_ID), text="Hello from Python 👋")

if __name__ == "__main__":
    asyncio.run(main())
