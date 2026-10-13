# DATA DEFECT NOTICE (2026-10-13)

The FTMO history in `data/market` holds one daily pseudo-bar from 2012-06-26 to 2021-01-20 that carries the next session's OHLC (look-ahead up to 24 hours). The raw store is unchanged on purpose; V2 builds a separate clean store.

Owner decision (V2 Gate B2): the **V1 Edge Program H01-H10 results are UNRELIABLE** (they used 2011-2021) and the **ML V0 historical evidence is CONTAMINATED**. Nothing is deleted or rerun. The machine-readable register is `XAUUSD-Machine learning/xau-edge-v2/docs/research/research_status_register.json`; the forensic report is `XAUUSD-Machine learning/reports/V2_DATA_PROVENANCE_FORENSIC_REPORT.md`.

Do not cite "no edge within budget" (Edge Program) or the ML V0 skill figures as evidence, in either direction.
