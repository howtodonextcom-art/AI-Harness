"""What is known about each pattern family: detector, causality, repaint class, research status.

One place, plain data. A family with no detector says so; nothing here implies the pattern has
predictive value. ``research_status`` follows the pattern-research classification: DETECTOR ONLY,
FUTURE RESEARCH CANDIDATE, DOCUMENT ONLY or REJECT (with the reason).
"""

# ruff: noqa: E501 - a table of prose notes; one entry per line reads best
from __future__ import annotations

from dataclasses import dataclass

NON_REPAINT_PROVEN = "NON_REPAINT PROVEN"
POTENTIAL_REPAINT = "POTENTIAL REPAINT"
UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class PatternStatus:
    key: str
    names: tuple[str, ...]  # lower-case names and aliases used by the sources
    detector: str | None  # dotted path of the implementation, or None
    causality: str  # how causality was shown, or why it is unknown
    repaint_class: str  # NON_REPAINT PROVEN / POTENTIAL REPAINT / REPAINTING / UNKNOWN
    research_status: str
    confirmation: str
    note: str


REGISTRY: tuple[PatternStatus, ...] = (
    PatternStatus(
        "WOLFE_WAVE",
        ("wolfe wave", "wolf wave", "wolfe"),
        "xau_edge.structure.wolfe.detect_wolfe_patterns",
        "prefix invariance proven on 2,520 cuts (default) and 14 series x 60 cuts (reclaim mode); peeking mutants fail",
        NON_REPAINT_PROVEN,
        "DETECTOR ONLY",
        "P5 pivot confirmed (3 bars after it forms) or, in LINE13_RECLAIM mode, the first close back inside line 1-3",
        "rules DISPUTED (P5 overshoot, entry, ETA); the author's reels draw entries at P5, before it can be known",
    ),
    PatternStatus(
        "DOUBLE_TOP_BOTTOM",
        ("double top", "double bottom", "adam and eve", "adam & eve", "eve and eve"),
        "xau_edge.structure.reversal.detect_reversals (kinds=DOUBLE); lifecycle: xau_edge.structure.formation",
        "prefix invariance of detections and of the lifecycle; parity with the detector 0 differences",
        NON_REPAINT_PROVEN,
        "FUTURE RESEARCH CANDIDATE (low prior; textbook gross R:R about 0.72)",
        "a close beyond the neckline after the second peak is confirmed",
        "Adam/Eve narrow-versus-rounded shapes are not distinguished",
    ),
    PatternStatus(
        "HEAD_AND_SHOULDERS",
        ("head and shoulders", "inverse head and shoulders", "head & shoulders"),
        "xau_edge.structure.reversal.detect_reversals (kinds=HNS)",
        "prefix invariance proven with the double top detector's harness",
        NON_REPAINT_PROVEN,
        "DETECTOR ONLY (7 events in 8 years of H1: untestable)",
        "a close beyond the sloped neckline after the right shoulder is confirmed",
        "",
    ),
    PatternStatus(
        "FALLING_WEDGE",
        ("falling wedge",),
        None,
        "no detector",
        POTENTIAL_REPAINT,
        "DOCUMENT ONLY (Bulkowski: a poor performer among bullish patterns)",
        "a close outside a trendline (Bulkowski)",
        "needs five trendline touches and line fitting",
    ),
    PatternStatus(
        "RISING_WEDGE",
        ("rising wedge",),
        None,
        "no detector",
        POTENTIAL_REPAINT,
        "DOCUMENT ONLY (Bulkowski: down breakouts rank last, 51% break-even failure)",
        "a close outside a trendline (Bulkowski)",
        "",
    ),
    PatternStatus(
        "CUP_AND_HANDLE",
        ("cup and handle", "cup & handle", "cup with handle"),
        None,
        "no detector",
        POTENTIAL_REPAINT,
        "DOCUMENT ONLY (curvature has no agreed measure; rare intraday)",
        "a handle breakout",
        "identification allows discretion (Bulkowski)",
    ),
    PatternStatus(
        "DIAMOND",
        ("diamond", "diamond top", "diamond bottom"),
        None,
        "no detector",
        POTENTIAL_REPAINT,
        "DOCUMENT ONLY (no formal shared definition)",
        "a break of an edge",
        "",
    ),
    PatternStatus(
        "TRIANGLE",
        ("triangle", "ascending triangle", "descending triangle"),
        None,
        "no detector",
        POTENTIAL_REPAINT,
        "DOCUMENT ONLY",
        "a close outside the boundary",
        "",
    ),
    PatternStatus(
        "FLAG",
        ("flag", "bull flag", "bear flag", "pennant"),
        None,
        "no detector",
        POTENTIAL_REPAINT,
        "DOCUMENT ONLY (pole and consolidation definitions vary; overlaps V1 H04)",
        "a breakout of the consolidation",
        "",
    ),
    PatternStatus(
        "HARMONIC",
        ("butterfly", "dragon", "three valleys and a river", "three valleys & a river"),
        None,
        "no detector",
        POTENTIAL_REPAINT,
        "DOCUMENT ONLY (Fibonacci ratios chosen by eye; entry at the unconfirmed completion point D)",
        "none: the author enters at completion",
        "",
    ),
    PatternStatus(
        "LIQUIDITY_SWEEP",
        ("liquidity sweep", "stop sweep", "liquidity grab", "failed breakout", "false breakout"),
        None,
        "none in this package (research_v2 tested sweeps as H07)",
        UNKNOWN,
        "REJECT as new research: it is Edge Program V2 H07 (closed, Stage 1 failed)",
        "a close back inside the level",
        "",
    ),
    PatternStatus(
        "BREAK_AND_RETEST",
        ("break and retest", "break & retest", "support resistance flip"),
        None,
        "no detector",
        UNKNOWN,
        "REJECT as new research: overlaps Edge Program V2 H08 (closed)",
        "a retest that holds",
        "",
    ),
)


def lookup(name: str) -> PatternStatus | None:
    wanted = name.strip().lower()
    for status in REGISTRY:
        if wanted == status.key.lower() or wanted in status.names:
            return status
    for status in REGISTRY:
        if any(wanted in alias or alias in wanted for alias in status.names):
            return status
    return None
