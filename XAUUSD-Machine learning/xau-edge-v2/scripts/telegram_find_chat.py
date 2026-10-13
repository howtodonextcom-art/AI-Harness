"""Find your Telegram chat id for the operational alerts (standard library only).

1. In Telegram, talk to @BotFather: /newbot, then copy the bot token.
2. Open the new bot and send it any message (for example /start).
3. Put the token in .env as XAU_V2_TELEGRAM_BOT_TOKEN=..., then run:  python scripts/telegram_find_chat.py
4. Put the printed id in .env as XAU_V2_TELEGRAM_CHAT_ID=..., then run scripts/telegram_test.py.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ENV = Path(__file__).resolve().parents[1] / ".env"


def token() -> str:
    lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    for raw in lines:
        if raw.strip().startswith("XAU_V2_TELEGRAM_BOT_TOKEN="):
            return raw.split("=", 1)[1].strip().strip("\"'")
    return ""


def main() -> int:
    bot = token()
    if not bot:
        print("XAU_V2_TELEGRAM_BOT_TOKEN is not set in .env")
        return 2
    try:
        url = f"https://api.telegram.org/bot{bot}/getUpdates"
        with urllib.request.urlopen(url, timeout=15) as r:  # noqa: S310
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"could not reach Telegram: {type(exc).__name__}")
        return 3
    seen: dict[int, str] = {}
    for update in data.get("result", []):
        chat = (update.get("message") or update.get("channel_post") or {}).get("chat") or {}
        if "id" in chat:
            seen[chat["id"]] = (
                chat.get("title") or chat.get("username") or chat.get("first_name") or ""
            )
    if not seen:
        print("no chats yet: send your bot a message (/start) and run this again")
        return 1
    for chat_id, name in seen.items():
        print(f"chat id {chat_id}  ({name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
