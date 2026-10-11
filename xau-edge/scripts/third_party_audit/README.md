# Third-party audits (not part of the package, not run in CI)

`smc_audit.py` and `smc_audit_vanishing_labels.py` apply a prefix-invariance test to the third-party package `smartmoneyconcepts` (joshyattridge, MIT). They need a separate environment:

```
uv venv .smcvenv && uv pip install --python .smcvenv/Scripts/python.exe smartmoneyconcepts numpy pandas
PYTHONIOENCODING=utf-8 .smcvenv/Scripts/python.exe scripts/third_party_audit/smc_audit.py
```

Do not install that package into the project environment (the live collector's venv). Results and scope: `docs/pattern-intelligence/detector-status.md`.
