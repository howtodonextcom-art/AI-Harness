# Data flow

Brief section 9: `RAW -> CLEAN -> RESAMPLED -> FEATURES`, deterministic at every step. This file
describes what exists today (Sprint 3) and marks what is still to come. Contracts live in
`system.md`; decisions in `docs/decisions/`.

```
          CSV / Parquet export                     MetaTrader 5 terminal (demo, read-only)
                  |                                           |
          FileBarSource                                Mt5BarSource  (DEMO guard, allowlist proxy,
                  \                                         /       drops the forming bar)
                   +------------- BarSource.fetch_bars ----+
                                        |  UTC bar-open timestamps, canonical schema
                                        v
              check_coverage / validate_bars   -> ValidationReport  (reports, never repairs)
                                        |
                                        v
                 RawStore.write   immutable Parquet + .meta.json   [RAW]
                                        |
                                        v
        DatasetCatalog.load   merge all fetches (newest wins) -> dataset_id   [CLEAN]
                                        |
                      +-----------------+------------------+
                      v                                    v
              resample_bars (M5 -> M15/H1/H4)     DatasetCatalog.sql (read-only DuckDB)
                      |                                    [RESAMPLED]
                      v
          cross_check vs broker bars
                      |
                      v
      features.indicators (pure NumPy functions)   [FEATURES, Sprint 3 part 1; versioned set in Sprint 4]
```

## Stages

| Stage | Module | Input -> output | Guarantees |
|---|---|---|---|
| Fetch | `market_data.mt5`, `market_data.importers` | request -> bar frame | UTC open times; no sorting, de-duplication or repair |
| Validate | `market_data.validators` | frame -> `ValidationReport` | 16 issue codes; ERROR = unfit for research; verdict is logged |
| Store (RAW) | `market_data.store` | frame -> Parquet + sidecar | content-addressed, write-once, read-only file, hash re-checked on read |
| Merge (CLEAN) | `market_data.catalog` | raw files -> one frame + `dataset_id` | newest fetch wins; duplicates counted; id changes when content changes |
| Resample | `market_data.resampling` | M5 -> M15/H1/H4 | server-clock buckets; incomplete buckets excluded and reported |
| Query | `DatasetCatalog.sql` | SQL -> frame | read-only, memory/thread limits, timeout, row cap |
| Features | `features.indicators` | arrays -> arrays | causal (no look-ahead), warm-up is `NaN`, inputs never mutated |

## Determinism and reproducibility

* Same raw files give the same `dataset_id` and byte-identical frames.
* Indicators are pure functions; golden tests pin them to TA-Lib output and a regression test pins
  the synthetic dataset hashes.
* Every stage that touches data emits a structured log event (`raw.write`, `validation.result`,
  `catalog.load`; see `xau_edge.observability`). Feature, model, signal, backtest and risk events
  are added with their epics (brief section 37).

## Not yet built

Feature sets keyed by `dataset_id` (Sprint 4), structure and regime labels (Sprint 5), pattern
windows and outcomes (Sprints 6-7), experiment registry (Sprint 7), backtests (Sprints 8-9).
