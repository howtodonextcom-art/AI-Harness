# ADR-0002: Polars + Parquet now, DuckDB for queries from Sprint 2

Status: accepted (2026-10-08), with a flagged risk

**Decision.** Use Polars (`>=2,<3`) for frames and Parquet for storage. DuckDB will provide SQL
over Parquet in Sprint 2. pandas is not a core dependency. PyArrow is deferred.

**Why.** Strict dtypes and explicit time-zone handling suit a data contract; Parquet is
columnar and reproducible; DuckDB reads Parquet directly.

**Risk.** Polars 2.0.0 was released 2026-10-06 (two days before this decision). Mitigations:
the Polars API is confined to the data layer, `uv.lock` pins the exact version, and 1.44.x is a
known fallback. Revisit after 2.0.x stabilises.
