"""Send ONE test message through the configured channel (reads .env). Operational text only."""

from __future__ import annotations

import socket
import sys
from datetime import UTC, datetime

from xau_edge_v2.config import Settings
from xau_edge_v2.ops.alerts import TelegramNotifier


def main() -> int:
    cfg = Settings()
    if cfg.telegram_bot_token is None or not cfg.telegram_chat_id:
        print("NOT CONFIGURED: set XAU_V2_TELEGRAM_BOT_TOKEN and XAU_V2_TELEGRAM_CHAT_ID in .env")
        return 2
    notifier = TelegramNotifier(cfg.telegram_bot_token.get_secret_value(), cfg.telegram_chat_id)
    stamp = f"{socket.gethostname()}, {datetime.now(UTC):%Y-%m-%d %H:%M} UTC"
    ok = notifier.send(f"XAU EDGE V2: kiểm tra kênh cảnh báo vận hành ({stamp}).")
    print("sent" if ok else f"FAILED: {notifier.last_error}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
