# ADR-0010: Indicators as pure NumPy functions, verified against recorded TA-Lib output

Status: accepted (2026-10-08)

**Context.** Epic 04 needs EMA, RSI, ATR, ADX, MACD, Stochastic and Bollinger bands. The brief says
"blindly trust indicator libraries" is forbidden (section 51) and lists TA-Lib in the stack
(section 8).

**Decision.** Implement the indicators ourselves in `xau_edge.features.indicators` as pure functions
over 1-D float arrays (warm-up `NaN`, causal, inputs untouched) and verify them against TA-Lib output
recorded once into `tests/fixtures/talib_golden.json`. TA-Lib stays out of the dependency tree.

**Why not depend on TA-Lib.** It needs a native library and wheels are not guaranteed on all of
Python 3.12-3.14 x Windows/Linux; the project's CI matrix and `uv sync --locked` would depend on it.
Owning ~300 lines gives full control over warm-up semantics and the repainting guarantee.

**Why not pandas-style ewm.** Conventions differ (seeding, Wilder smoothing, MACD alignment); we use
TA-Lib's, because it is the common reference and the golden tests make the convention explicit.

**Conventions worth remembering.**
* EMA is seeded with the SMA of the first `period` values; MACD seeds the fast EMA at the slow EMA's
  first index with the mean of the `fast` values ending there.
* RSI/ATR/ADX use Wilder's recursion; flat prices give RSI 0 (TA-Lib), ATR 0, ADX 0.
* Bollinger uses the population standard deviation; rolling volatility uses the sample deviation of
  log returns (project definition, no TA-Lib counterpart).
* Stochastic raw %K is 0 when the window has zero range.

**Regenerating the fixture.** In a scratch virtual environment (not the project's): `uv pip install
ta-lib numpy`, generate `default_rng(20251008)` random-walk OHLC (400 bars), call `talib.EMA/SMA/RSI/
TRANGE/ATR/ADX/PLUS_DI/MINUS_DI/MACD/STOCH(14,3,SMA,3,SMA)/BBANDS`, and write the inputs and outputs
as JSON with a provenance string. Only the JSON is committed.

**Consequences.** Any change to indicator maths shows up as a golden or regression failure. Python
loops in Wilder recursions are fine for current sizes (100k bars take well under a second per series);
revisit if tick data arrives.
