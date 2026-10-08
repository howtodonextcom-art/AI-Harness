"""SNTP clock check with a fake transport (no network)."""

from __future__ import annotations

import pytest

from xau_edge.ops.clock_check import (
    ClockCheckResult,
    build_request,
    check_clock,
    clock_alert,
    parse_offset,
    to_ntp_timestamp,
)

pytestmark = pytest.mark.unit

NOW = 1_800_000_000.0


def reply(t2: float, t3: float, *, mode: int = 4, stratum: int = 2) -> bytes:
    head = bytes([mode, stratum]) + bytes(30)
    return head + to_ntp_timestamp(t2) + to_ntp_timestamp(t3)


class FakeNtp:
    """Server whose clock is ``skew`` seconds ahead of ours; the 'network' takes no time."""

    def __init__(self, skew: float, *, fail: bool = False) -> None:
        self.skew = skew
        self.fail = fail

    def exchange(self, server: str, packet: bytes, timeout: float) -> bytes:
        if self.fail:
            msg = "timed out"
            raise TimeoutError(msg)
        return reply(NOW + self.skew, NOW + self.skew)


def test_request_shape() -> None:
    packet = build_request(NOW)
    assert len(packet) == 48
    assert packet[0] == 0x1B


def test_zero_offset_and_known_skew() -> None:
    zero = check_clock(["a"], transport=FakeNtp(0.0), clock=lambda: NOW)
    assert zero.offset_seconds == pytest.approx(0, abs=1e-6)
    skewed = check_clock(["a"], transport=FakeNtp(7.5), clock=lambda: NOW)
    assert skewed.offset_seconds == pytest.approx(7.5, abs=1e-6)
    assert skewed.exceeds()


def test_median_of_servers_ignores_one_liar_and_one_failure() -> None:
    class Multi:
        def exchange(self, server: str, packet: bytes, timeout: float) -> bytes:
            skew = {"a": 0.2, "b": 120.0, "c": 0.1}.get(server)
            if skew is None:
                msg = "down"
                raise OSError(msg)
            return reply(NOW + skew, NOW + skew)

    r = check_clock(["a", "b", "c", "d"], transport=Multi(), clock=lambda: NOW)
    assert r.servers_ok == 3
    assert r.offset_seconds == pytest.approx(0.2, abs=1e-6)
    assert len(r.errors) == 1


def test_all_servers_failing_is_unknown_not_ok() -> None:
    r = check_clock(["a", "b"], transport=FakeNtp(0, fail=True), clock=lambda: NOW)
    assert r.offset_seconds is None
    assert not r.exceeds()
    alert = clock_alert(r)
    assert alert is not None
    assert alert.severity == "warning"


@pytest.mark.parametrize(
    "bad",
    [b"short", reply(NOW, NOW, mode=3), reply(NOW, NOW, stratum=0), bytes([4, 2]) + bytes(46)],
)
def test_malformed_replies_are_rejected(bad: bytes) -> None:
    with pytest.raises(ValueError, match=r"SNTP|stratum|server|zero"):
        parse_offset(bad, NOW, NOW)


def test_alert_levels() -> None:
    assert clock_alert(ClockCheckResult(1.0, 2)) is None
    alert = clock_alert(ClockCheckResult(-6.0, 2))
    assert alert is not None
    assert (alert.code, alert.severity) == ("CLOCK_DRIFT", "critical")
