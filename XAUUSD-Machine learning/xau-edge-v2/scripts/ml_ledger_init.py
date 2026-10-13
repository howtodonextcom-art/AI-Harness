"""Register the K family K_V2_VOL_V0 in the ledger for the CURRENT frozen spec hash (idempotent).

Run once after a spec version is frozen and before any confirmatory run. It writes no data access.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from xau_edge_v2.ml import guard

spec = json.loads(guard.SPEC.read_text(encoding="utf-8"))
k = spec["k_accounting"]
digest = guard.spec_hash()
ledger = guard.load_ledger()
existing = ledger["families"].get(guard.FAMILY)
if existing and existing.get("spec_hash") == digest:
    print("already registered for this spec hash:", digest)
else:
    ledger["families"][guard.FAMILY] = {
        "k": k["k"],
        "candidates": k["candidates"],
        "alpha_family": k["alpha_family"],
        "alpha_per_comparison": k["alpha_per_comparison"],
        "spec_version": spec["spec_version"],
        "spec_hash": digest,
        "adr": "ADR-V2-007",
        "registered_at": datetime.now(UTC).isoformat(),
    }
    ledger["events"].append(
        {
            "ts": datetime.now(UTC).isoformat(),
            "kind": "FAMILY_REGISTERED",
            "detail": {"family": guard.FAMILY, "spec_hash": digest, "candidates": k["candidates"]},
        }
    )
    guard._write(guard.LEDGER, ledger)  # noqa: SLF001 - the ledger's own atomic writer
    print("registered", guard.FAMILY, digest)
