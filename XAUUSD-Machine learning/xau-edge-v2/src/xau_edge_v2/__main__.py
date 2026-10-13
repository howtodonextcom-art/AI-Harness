"""``python -m xau_edge_v2``: serve the API, the WebSocket and the built web page on one port."""

from __future__ import annotations

import uvicorn

from xau_edge_v2.config import Settings


def main() -> None:
    cfg = Settings()
    print(f"XAU EDGE v2 (PAPER) on http://{cfg.host}:{cfg.port}  data(read-only)={cfg.data_root}")
    uvicorn.run("xau_edge_v2.api.app:create_app", factory=True, host=cfg.host, port=cfg.port,
                log_level="warning")  # fmt: skip


if __name__ == "__main__":
    main()
