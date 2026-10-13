# ADR-0023: Local web control plane

Status: accepted (2026-10-08). Supersedes the section "API and operator control" of ADR-0019 (only
the sentence "No new write API route is part of the initial demo execution track"); every other part
of ADR-0019 stays in force, in particular: the kill switch is never reset from the API, and a tripped
kill switch does not close positions by itself.

**Problem.** Running the demo bot needed a terminal for every step: preflight checks scattered over
several scripts, `demo_trader.py` started by hand (or NSSM), `.env` edited to move between dry-run
and DEMO, a separate smoke script, and no quick "stop everything" for the owner. The dashboard could
only watch.

**Decision.** An opt-in control plane on the existing local API, `/control/*`, mounted only when
`XAU_EDGE_WEB_CONTROL=true` (default false). It offers exactly five things:

1. **Preflight** (`GET /control/preflight`): every operating condition as a list of checks
   (ok/warn/fail/unknown) with a Vietnamese fix hint. The terminal is contacted read-only
   (initialize, account_info, terminal_info, shutdown through the query-only proxy) with a timeout,
   and only when no bot holds the lock; otherwise facts come from `status.json`.
2. **Lifecycle** (`POST /control/bot/start|stop|restart`, `GET /control/bot`): one bot process, via
   NSSM (`nssm start|stop xau-edge-bot`, fixed arguments) when the service is installed, else a
   detached `scripts/demo_trader.py` child. The bot's lock file is the single truth for "running".
   Stop is soft: a stop request file ends the loop after the current cycle; terminate only after a
   timeout.
3. **Mode** (`POST /control/mode`, body `{"mode": "DRY_RUN"|"DEMO"}`): the choice is written to
   `data/execution/runtime_mode.json`, which the bot reads at start. `.env` stays the upper bound
   (no demo trading in `.env` means DRY-RUN whatever the file says) and is never written. The file
   can only hold DRY_RUN or DEMO; FUNDED and LIVE are rejected by the request model, the file
   validator and the bot. A funded `.env` ignores the file. DEMO needs the typed word `DEMO`, a
   fresh preflight with the terminal, the account in the whitelist, a demo account, Algo Trading on,
   the trade password present and the kill switch clear; the switch is confirmed by `status.json`.
4. **Smoke** (`POST /control/smoke`, typed `SMOKE`): the existing labelled 0.01-lot smoke order
   (`build_smoke_intent` + `Mt5DemoExecutor.submit_smoke`), closed after a few seconds and
   reconciled; at most one per 10 minutes and five per Prague day, never with an open bot position,
   never in the FTMO guard windows or a news window. `.env` must still allow smoke.
5. **Flatten** (`POST /control/flatten`, typed `FLATTEN`): trips the kill switch (`WEB_FLATTEN`)
   first, stops the bot, closes each bot-owned position through `close_position` (state + magic;
   manual positions are never touched), reconciles and lists what is still open. No automatic
   restart; the reset stays the CLI command.

**Security.** API bound to 127.0.0.1; `/control` requires `Host` = `127.0.0.1:<port>` or
`localhost:<port>` (DNS rebinding), a random token generated at each API start and stored in
`data/execution/control_token` (current user only), and for POST an allowed `Origin`, JSON
`Content-Type` and an `Idempotency-Key`; all checked by a middleware before any route code. The
dashboard's Next.js server reads the token file and proxies; the token is never in the browser
bundle. Long actions are jobs (one state-changing job at a time, idempotent by key). Every action
is journaled with `source="web"`. Responses carry codes and short messages, never stack traces,
paths or secrets; account numbers appear only as their last three digits.

**Not offered, by design.** Choosing FUNDED or LIVE, resetting the kill switch, arbitrary order
parameters, editing `.env`, remote access, Telegram control.

**Consequences.** The route-table test now lists the six `/control` POST routes (only when enabled)
and asserts that no route names funded, live, reset or env. Under NSSM, DEMO from the web needs the
service installed with `-ConfirmMode DEMO` (the web never changes NSSM parameters); in DRY-RUN that
flag is harmless. The bot stays fully usable from the CLI exactly as before.
