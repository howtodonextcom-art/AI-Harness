# ADR-0018: Read-only API, dashboard, paper trading, and no live execution

Status: accepted (2026-10-08)

**API.** FastAPI on 127.0.0.1 only, CORS limited to the local dashboard origins and GET. All routes are
GET except `POST /paper/orders`, which takes no trade parameters (extra fields are a 422), derives the
decision from the server-side signal, and reaches only the paper broker. A test walks the route table
and requires exactly that one write route. Heavy endpoints (signals, patterns) are cached per M15
decision bar in a bounded LRU and limited to two concurrent computations; `at` must lie inside the
data range.

**Dashboard.** Next.js (App Router), TypeScript strict, Tailwind, TradingView Lightweight Charts. It
only reads. It shows the decision with its reasons, probabilities labelled as uncalibrated analogue
frequencies, bias per timeframe, regime, the analogue overlay (what followed is context only), the
explanation with a reproduction hash, validation status, staleness of the data, and a paper account
panel. Failures leave a visible banner and dim the old figures instead of looking healthy.

**Paper trading.** `PaperExecutionBroker` mirrors the backtest fill rules; `PaperTrader` is the
only path from signal to order and applies the risk engine and `ExecutionSafety` (environment,
account, symbol, lot and order-count limits, dry-run). The broker interface is the abstraction a live
broker would implement; none is implemented.

**No live execution.** Not in this project: no broker order API is imported anywhere under
`execution/`, `Settings` forbids the live flag, the API has no order route beyond the paper one. This
is a decision, not an omission: no strategy has passed validation, and live trading would need that
evidence, a measured cost model, a persistent kill switch, an independent review and an explicit owner
decision.

**Known limits.** The kill switch and paper state are in-memory; the trader passes
`news_blocked=False` to the risk engine because a BUY/SELL signal can only exist after the signal's own
news check passed (`NEWS_UNKNOWN` forces WAIT); the dashboard has type-check, lint and build checks
and was inspected with real data at 1440x900 and 390 px, but has no automated browser test in CI.
