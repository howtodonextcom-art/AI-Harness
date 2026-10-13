"""The live socket: ``hello``, then ``live`` (new quote / forming bars), ``state`` (the decision
changed) and ``heartbeat`` events. ``seq`` rises by one per event so a client detects a gap and
refetches over REST; the socket never carries the decision itself, only the fact that it changed."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import WebSocket, WebSocketDisconnect

from xau_edge_v2.api.context import AppContext
from xau_edge_v2.api.state import build_state
from xau_edge_v2.domain.contract import Timeframe, WsEvent

Kind = Literal["hello", "heartbeat", "live", "state", "paper", "human"]


async def serve_socket(socket: WebSocket, ctx: AppContext, allowed: set[str]) -> None:
    cfg = ctx.settings
    origin = socket.headers.get("origin")
    if origin is not None and origin not in allowed:
        await socket.close(code=1008)  # policy violation: a foreign web page may not listen
        return
    await socket.accept()
    seq = -1

    async def send(kind: Kind, **extra: Any) -> None:
        nonlocal seq
        seq += 1
        version = ctx.data_version(ctx.store.coverage(Timeframe.M1))
        event = WsEvent(type=kind, seq=seq, ts=datetime.now(UTC), data_version=version, **extra)
        await socket.send_text(event.model_dump_json())

    def fingerprint() -> str:
        return build_state(ctx).model_dump_json(exclude={"generated_at", "decision_id"})

    try:
        await send("hello")
        # baselines come BEFORE the slow fingerprint: a change made meanwhile is still announced
        last_live = ctx.live.updated_at()
        last_paper = ctx.desk.store.revision()
        last_human = ctx.desk.store.human_revision()
        last_state = await asyncio.to_thread(fingerprint)
        tick = min(cfg.live_poll_seconds, cfg.heartbeat_seconds)
        now = time.monotonic()
        next_beat, next_state = now + cfg.heartbeat_seconds, now + cfg.state_poll_seconds
        while True:
            await asyncio.sleep(tick)
            if (updated := ctx.live.updated_at()) != last_live:
                last_live = updated
                await send("live", quote=ctx.live.quote(ctx.calendar), forming=ctx.live.forming())
            if (paper := ctx.desk.store.revision()) != last_paper:
                last_paper = paper
                await send("paper")
            if (human := ctx.desk.store.human_revision()) != last_human:
                last_human = human
                await send("human")
            now = time.monotonic()
            if now >= next_state:
                next_state = now + cfg.state_poll_seconds
                current = await asyncio.to_thread(fingerprint)
                if current != last_state:
                    last_state = current
                    await send("state")
            if now >= next_beat:
                next_beat = now + cfg.heartbeat_seconds
                await send("heartbeat")
    except (WebSocketDisconnect, RuntimeError):
        return
