# ADR-0003: Python >= 3.12, managed with uv

Status: accepted (2026-10-08)

**Decision.** `requires-python = ">=3.12,<3.15"`; environments and locking via `uv`.

**Why.** numpy 2.5 and XGBoost 3.4 require 3.12+. `uv` provides fast, locked environments on Windows.

**Known gap.** Only Python 3.14.4 was available during Sprint 1; 3.12 and 3.13 are untested.
Sprint 2 adds them to a CI matrix. `make` is absent on Windows, so `scripts/dev.ps1` mirrors the Makefile.
