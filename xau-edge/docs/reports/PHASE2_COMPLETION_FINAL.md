# Phase 2 completion — paper terminal consolidated, edge still UNVALIDATED

Ngày: 2026-10-11 (GMT+7). Baseline git lúc bắt đầu sprint: `03b7a0e` trên `d732602` trên `a004958`.
Working tree sau sprint **chưa commit**. LIVE `:8000`/`:3000` đang chạy **build working-tree** (dashboard `next build` + restart stack khi thị trường CLOSED), không phải SHA đã push.

## Verdict

**PHASE 2 COMPLETE — PAPER TERMINAL CONSOLIDATED, EDGE STILL UNVALIDATED**

Không gọi sản phẩm “xong” vì UI đẹp. Đường PAPER live đã gộp: `data/market` → TradeEngine → TradingSignal v2 → ExecutionIntent → PaperDesk. Guard UNKNOWN / flatten / daily-loss đã nối. Edge vẫn UNVALIDATED. Forward vẫn F0, độ phủ 48.6% < cổng 95%. Demo không sẵn sàng.

Independent review (không phải author): [canonical brain / schema / guards](38cd38f8-9946-4578-acca-48d612b089b8) — 5/6 PASS; item UNKNOWN UI FAIL rồi **đã sửa** (`HeroState` + `HERO_VI` + copy riêng, không crash `TerminalView`).

---

## Completion matrix

| Item | Status | Evidence |
|---|---|---|
| PHASE 1 AUDIT | **COMPLETE** | `CONSOLIDATION_AUDIT_AND_EDGE_PATH.md` §15 CLOSED. Santa 3 vòng; không vòng 4 (S3 BLOCKED-by-policy). ADR 0026–0030 tồn tại rồi ACCEPTED. |
| HERO B | **COMPLETE** | Code: `honesty.ts`, `HeroCard`/`DecisionPanel`. LIVE DOM 2026-10-11: `UNVALIDATED · phủ 48.6% / 95%`, Entry/SL/TP/R:R (— vì CHỜ), action CHỜ, bias trên fold. Không redesign. |
| LIVE DEPLOY | **COMPLETE** | Market CLOSED. `stop_market_stack.ps1` → `npm run build` → `start_market_stack.ps1 -Dashboard -NoTerminal`. Health GOOD. `:8000` `source_mode=LIVE`, `:3000/trade` 200. Browser 1440 và 1920. |
| K CAP | **COMPLETE** | Ledger V2: **K cap = 24**. `_v2_k_cap` (`research/service.py:175-192`) ledger thắng STATE. Test mismatch vẫn xanh. |
| TRADING SIGNAL V2 | **COMPLETE** | Additive: `schema_version=2`, `source_mode`, `setup_phase`, `entry_basis`, aliases. Unknown version fail. `read_signal_record` đọc journal cũ. Goldens regenerated. |
| EXECUTION INTENT | **COMPLETE** | `intent_from_signal` copy geometry. Paper / Demo dry-run / Funded disabled. Không gửi lệnh. |
| SIZING | **COMPLETE** | Canonical `size_for_risk`. `risk.sizing.position_size` wrap. Parity test cùng equity/risk/entry/SL/spec → cùng lot. |
| DECISION PARITY | **PARTIAL** | `scripts/decision_parity.py --synthetic` PASS, 0 BUG. Walk LIVE window **chưa wire**. Demo vẫn không consume engine ở runtime. |
| DATA STORES | **COMPLETE** | `data/market` live. `data/raw/MANIFEST.json` (75 file). `data/research_history/MANIFEST.json` (6 file). Không store thứ tư. Không xoá. |
| UNKNOWN FAIL-CLOSED | **COMPLETE** | `market_open` chỉ OPEN. `MARKET_UNKNOWN` ≠ CLOSED/STALE/UNAVAILABLE. WAIT+`UNKNOWN_STATE`. Hero `UNKNOWN` → action UNAVAILABLE. UI map đã thêm. |
| FLATTEN REQUIRED | **COMPLETE** | `paper_desk._manage` gán `daily_loss_guard=flatten_required`. Close `DAILY_LOSS_GUARD`, journal. Test FAIL-then-pass. Không broker. |
| DAILY LOSS GUARD | **COMPLETE** | New open: `governor.check` → `DAILY_LIMIT`. API `limits.daily_loss_guard` / `flatten_required`. UI giải thích block. Không invent FTMO. |
| FREEZE LIVE | **COMPLETE** | `AGENTS.md`, `CLAUDE.md`, `docs/operations/market-data-operations.md`, ADR-0029 ACCEPTED. |
| TASK SCHEDULER | **COMPLETE** | `XAU-EDGE Market Stack` Enabled/Ready, At logon, Start In repo, `-Dashboard`, RestartCount 3, IgnoreNew, Last Result 0. Không thay NSSM. |
| LEGACY ENGINE | **PARTIAL** | Marked DEPRECATED. Runtime còn: `demo_trader.py`, `/paper/*` (`api/app.py`), `current_signal.py`, `forward_test.py`. Không xoá. |
| UI PRUNING | **COMPLETE** | Fold: action/bias/evidence/coverage/levels. Ops ở tab Hệ thống. Không health block lớn trên fold. |
| SYSTEM HEALTH | **COMPLETE** | Tab Hệ thống: MT5, collector, parity, tick, disk, API, coverage, news, writer lock, strategy, source, dashboard, DEMO LOCKED. |
| CI | **PARTIAL** | Local: ruff+mypy trên core PASS; 15 golden/v2/guard tests PASS; dashboard `tsc`+`next build` PASS. Full `pytest -m "not mt5"` không chạy hết lại sau golden regen (trước đó 363 pass / 1 golden fail — fail đã sửa). Main GitHub chưa push working tree. |
| EDGE | **COMPLETE** (as UNVALIDATED) | Không giả thuyết mới. V3 chỉ template. Test-H/holdout không đụng. Dev n=135 vẫn không chứng minh directional edge. |
| FORWARD | **PARTIAL** | F0. `LIVE ACTIONABLE SIGNAL NOT YET OBSERVED`. Coverage 48.64% (232/477), gaps 30′ + 215′. Replay không nâng level. Cổng 95% giữ. |
| DEMO READINESS | **DEFERRED** | Dry-run adapter tồn tại nhưng **không** thay `generate_signal`. 0 unexplained live-window differences chưa chứng minh. Flag DEMO vẫn false. |

---

## Scores (không trung bình Edge vào UI)

| Trục | Điểm / 10 | Ghi chú |
|---|---|---|
| Engineering completeness | 8 | Contract, intent, guards, sizing, freeze-LIVE, LIVE deploy. Parity LIVE window còn thiếu. |
| Trader product completeness | 7 | 5-giây: CHỜ + UNVALIDATED + LIVE + levels. Chưa quan sát MUA/BÁN live. |
| Architecture consolidation | 7 | Một não PAPER. Legacy còn runtime importer. |
| Operational readiness | 8 | Task Scheduler Ready; stack sống sau restart; disk C: 13.4 GB WARN. |
| Forward evidence | 2 | F0, 48.6% coverage. Không bịa. |
| Edge readiness | 1 | UNVALIDATED. Không cơ chế mới. |
| Demo readiness | 2 | Adapter dry-run only. Bot/flags khoá. Parity live chưa có. |

---

## 12 câu hỏi

1. **Còn hơn một trading brain?** Có. PAPER live = TradeEngine. Legacy `generate_signal` vẫn phục vụ `/paper/*` và `demo_trader.py` (DEPRECATED, không xoá).
2. **Legacy còn gì, vì sao?** `signals.engine`, `trading/adapter.py`, `execution/bridge.py` (double-spread nếu dùng với TradingSignal), `/paper/*`, `PaperTrader` $100k, `demo_trader.py`. Chưa đủ: 0 runtime caller + parity live + CI xanh trên đường mới.
3. **TradingSignal đã là contract canonical?** Có, trên đường PAPER live / replay acceptance. Journal đọc v1+v2.
4. **Demo dry-run đã consume canonical intent?** Chưa ở runtime. `DemoDryRunAdapter` + harness synthetic có. `demo_trader.py` vẫn `generate_signal`.
5. **BUY/SELL vẫn UNVALIDATED?** Có. `validated_edge=false`. Label `UNVALIDATED_OPERATIONAL_BASELINE`.
6. **UNKNOWN có bao giờ authorize entry?** Không. `market_open` chỉ OPEN; `UNKNOWN_STATE`; hero UNKNOWN → UNAVAILABLE.
7. **flatten / daily-loss đã wire?** Có. Flatten → manager close paper. Daily-loss stop → chặn open mới + UI.
8. **LIVE chạy build verified mới?** Có trên máy: dashboard rebuild + stack restart khi CLOSED. SHA git vẫn `03b7a0e` vì chưa commit/push.
9. **Forward coverage valid?** Có nghĩa là **trung thực và chưa đủ**. 48.6% < 95%. Không backfill.
10. **Chặn Demo đúng cái gì?** Không edge; evidence gate; flags off; dry-run mặc định; adapter chưa thay bot; parity live 0 BUG chưa có; không gửi lệnh.
11. **Chặn validated Edge đúng cái gì?** Không cơ chế mới; Dev không có directional edge; Test-H/holdout khoá; K cap 24; V3 chỉ template.
12. **Sprint sau được xoá gì?** Chỉ sau 0 runtime+research caller, parity live, docs/CI: `to_legacy_signal` execution use, `/paper` PaperTrader, rồi `generate_signal` callers. Không xoá `data/raw` / `data/research_history`.

---

## LIVE acceptance (thị trường CLOSED)

- `:8000/trade/decision`: `source_mode=LIVE`, `market.open=false`, `hero=MARKET_CLOSED`, action WAIT, coverage 48.64%, `validated_edge=false`.
- `:3000/trade` DOM: `DỮ LIỆU LIVE · ĐÓNG CỬA`, `UNVALIDATED · phủ 48.6% / 95%`, CHỜ, PAPER không lệnh thật, Entry/SL/TP/R:R = —.
- Tab Hệ thống: MT5 OK (FTMO-Demo read-only), collector GOOD, DEMO LOCKED (`DEMO_TRADING_DISABLED`, `DEMO_DRY_RUN`), F0, writer lock OK.
- **LIVE ACTIONABLE SIGNAL NOT YET OBSERVED.** Không giả MUA/BÁN.

---

## ADR

| ADR | Status |
|---|---|
| 0026 canonical brain | ACCEPTED (`docs/decisions/0026-canonical-brain-direct-intent.md`) |
| 0027 one live store | ACCEPTED |
| 0028 TradingSignal v2 | ACCEPTED |
| 0029 freeze-LIVE | ACCEPTED |
| 0030 K cap + V3 template | ACCEPTED (ledger 24; template only) |
| 0031 UNKNOWN / flatten / daily-loss | ACCEPTED |
| drafts 0026–0030 | SUPERSEDED as working copy (rationale kept) |

---

## Không làm (đúng scope)

Không gửi MT5; không bật DEMO/FUNDED; không mở Test-H/holdout; không tune v1.1; không xoá `data/raw` hay `data/research_history`; không indicator/BOS/ML/LLM; BE/trailing vẫn OFF.
