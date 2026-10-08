"""System clock check against NTP servers (pure-python SNTP, no extra dependency).

Why: bar timing, broker-clock conversion and the ``data_age`` gate all assume the PC clock is
right. The caller (the bot loop) trips the kill switch or blocks new orders when the offset is
larger than ``MAX_OFFSET_SECONDS`` (5 s). Servers are queried through an injectable transport so
tests never touch the network. A failed check returns ``offset_seconds=None`` (unknown), which the
caller should treat as a warning, never as "all clear".
"""

from __future__ import annotations

import socket
import statistics
import struct
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from xau_edge.execution.status import Alert

MAX_OFFSET_SECONDS = 5.0
NTP_PORT = 123
NTP_UNIX_DELTA = 2_208_988_800  # seconds between 1900-01-01 and 1970-01-01
DEFAULT_SERVERS: tuple[str, ...] = ("time.windows.com", "pool.ntp.org", "time.cloudflare.com")
_PACKET_LEN = 48
_CLIENT_HEADER = 0x1B  # LI=0, VN=3, mode=3 (client)


class SntpTransport(Protocol):
    """Send one SNTP request packet to ``server`` and return the reply bytes."""

    def exchange(self, server: str, packet: bytes, timeout: float) -> bytes:
        """Raise ``OSError`` on failure."""
        ...


class UdpTransport:
    """Real UDP transport."""

    def exchange(self, server: str, packet: bytes, timeout: float) -> bytes:
        """Send ``packet`` and wait for the reply."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.sendto(packet, (server, NTP_PORT))
            data, _ = sock.recvfrom(1024)
        return data


@dataclass(frozen=True)
class ClockCheckResult:
    """Outcome of a clock check."""

    offset_seconds: float | None
    """Median offset (server minus local, seconds); None when no server answered."""
    servers_ok: int
    errors: tuple[str, ...] = field(default_factory=tuple)

    def exceeds(self, limit: float = MAX_OFFSET_SECONDS) -> bool:
        """True when the offset is known and its magnitude is above ``limit``."""
        return self.offset_seconds is not None and abs(self.offset_seconds) > limit


def to_ntp_timestamp(unix_seconds: float) -> bytes:
    """Encode a Unix time as an 8-byte NTP timestamp."""
    ntp = unix_seconds + NTP_UNIX_DELTA
    whole = int(ntp)
    frac = int((ntp - whole) * 2**32)
    return struct.pack("!II", whole, frac)


def _from_ntp(raw: bytes) -> float:
    whole, frac = struct.unpack("!II", raw)
    return float(whole - NTP_UNIX_DELTA + frac / 2**32)


def build_request(now: float) -> bytes:
    """48-byte SNTP client request carrying our transmit time."""
    return bytes([_CLIENT_HEADER]) + bytes(39) + to_ntp_timestamp(now)


def parse_offset(reply: bytes, sent_at: float, received_at: float) -> float:
    """Clock offset (server minus local) from a reply: ((t2 - t1) + (t3 - t4)) / 2."""
    if len(reply) < _PACKET_LEN:
        msg = f"short SNTP reply ({len(reply)} bytes)"
        raise ValueError(msg)
    if (reply[0] & 0x07) not in (4, 5):
        msg = "reply is not a server-mode SNTP packet"
        raise ValueError(msg)
    if reply[1] == 0:
        msg = "kiss-of-death or unsynchronised server (stratum 0)"
        raise ValueError(msg)
    t2 = _from_ntp(reply[32:40])
    t3 = _from_ntp(reply[40:48])
    if reply[40:48] == bytes(8):
        msg = "server sent a zero transmit timestamp"
        raise ValueError(msg)
    return ((t2 - sent_at) + (t3 - received_at)) / 2


def check_clock(
    servers: Sequence[str] = DEFAULT_SERVERS,
    *,
    transport: SntpTransport | None = None,
    timeout: float = 3.0,
    clock: Callable[[], float] = time.time,
) -> ClockCheckResult:
    """Query every server and return the median offset. Never raises."""
    link = transport or UdpTransport()
    offsets: list[float] = []
    errors: list[str] = []
    for server in servers:
        try:
            sent = clock()
            reply = link.exchange(server, build_request(sent), timeout)
            offsets.append(parse_offset(reply, sent, clock()))
        except (OSError, ValueError, struct.error) as exc:
            errors.append(f"{server}: {type(exc).__name__}")
    offset = statistics.median(offsets) if offsets else None
    return ClockCheckResult(offset, len(offsets), tuple(errors))


def clock_alert(result: ClockCheckResult, limit: float = MAX_OFFSET_SECONDS) -> Alert | None:
    """CRITICAL when the offset exceeds ``limit``, WARNING when it could not be measured."""
    if result.offset_seconds is None:
        return Alert("CLOCK_UNVERIFIED", "warning", "no NTP server answered; clock not verified")
    if result.exceeds(limit):
        return Alert(
            "CLOCK_DRIFT",
            "critical",
            f"system clock is {result.offset_seconds:+.1f}s off NTP (limit {limit:g}s)",
        )
    return None
