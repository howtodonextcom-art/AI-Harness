# Final completion ledger (2026-10-11)

Scores are the exact weighted sums of the rubric in `FINAL_99_PRODUCT_COMPLETION_AND_MCP_QA.md` section 4 (weights fixed in advance). "Before" of iteration 1 is the state at `451dcb8`, which the earlier checkpoint reported without a score; it is estimated from the open items at that time and marked (est.).

| Iter | Issues opened | Issues closed | Tests | MCP result | Review / red team | Product before | Product after |
|---:|---|---|---|---|---|---:|---:|
| 1 | stale live build; ambiguous session labels | live rebuilt and restarted (market CLOSED); labels Tokyo / London / New York | mock 336/336 (sandbox), acceptance 31/31 | live MARKET_CLOSED, 390 and 1440 screenshots, console clean | self | 84 (est.) | 88 |
| 2 | WAIT to SELL transition froze the tab (FIX-01) | allocator replaced, regression unit test, rapid-transition test | unit 24/24, overlay 7/7 | CDP pause located the loop | self red team: levels outside the visible range | 88 | 91 |
| 3 | badge over TP1 (FIX-02); legend over plan labels at 390 (FIX-03); label far from its line | slot allocator with priority, inset and 40 px cap | overlay 11/11 | BUY, SELL, key-levels screenshots, 390 emulation | self | 91 | 93 |
| 4 | expired plan figures (FIX-04); WAIT `missing` (FIX-05); HOLD levels (FIX-06) | all three | cockpit tests, overlay 12/12 | EXPIRED, HOLD, EXIT, STALE, collector_down in the real browser | self red team: expired plan used | 93 | 94.5 |
| 5 | CLS 0.23 (FIX-07); 10 unnamed fields (FIX-08) | both | layout stability 3/3 (red before, green after) | trace and layout-shift sources | self | 94.5 | 95.5 |
| 6 | stale build undetectable (FIX-09); terminology (FIX-10); research infrastructure | build stamp and test; wording; ledger, fill, room, waterfall | decision_research 63/63 + 4 room tests | n/a | self | 95.5 | 96.0 |
| 7 | final verification at `86338bf` | none new | mock 351/351, acceptance 31/31, python gate 2834 passed | live smoke: sha 86338bf, CLS 0, console clean, 390 and 1440 | self | 96.0 | 96.0 |

Open at the end: CRITICAL 0, HIGH 0, MEDIUM correctness 0, MEDIUM other 0, LOW/cosmetic 2 (200% zoom: the action badge sits over the lowest candles when no free band exists; one transient `ERR_NO_BUFFER_SPACE` after about 4,000 requests in one tab). External: slippage evidence, commission schedule, tick history before 2021-10, a truly independent reviewer, owner authorization for any V4 charter, the push.
