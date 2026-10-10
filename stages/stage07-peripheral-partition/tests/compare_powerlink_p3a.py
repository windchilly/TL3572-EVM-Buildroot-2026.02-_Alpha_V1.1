#!/usr/bin/env python3
"""Compare real P3a libraries/full objects across two independent builds."""
import argparse
import hashlib
import json
from pathlib import Path

ARTIFACTS = (
    "aarch64/core/libm7_powerlink_mn_core.a", "aarch64/libm7_powerlink_passive_mn.a", "mn-passive-full.o",
    "p2/p1/core/aarch64/libm7_powerlink_mn_core.a", "p2/p1/core/aarch64/mn-core.o",
    "p2/p1/edrv-aarch64/libm7_powerlink_eth2_edrv.a", "p2/p1/mn-core-edrv.o",
    "p2/rtos-aarch64/libm7_powerlink_rtos.a", "p2/mn-core-edrv-rtos.o",
)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    results = []
    for name in ARTIFACTS:
        a, b = (args.first / name).read_bytes(), (args.second / name).read_bytes()
        if a != b:
            raise SystemExit(f"NOT identical: {name}")
        results.append({"path": name, "bytes": len(a), "sha256": hashlib.sha256(a).hexdigest()})
    args.report.write_text(json.dumps({"phase": "P3a SOFTWARE ONLY", "identical": True, "artifacts": results}, indent=2) + "\n", encoding="utf-8")
    print(f"P3a REPRO PASS: {len(results)} artifacts byte identical; no firmware or board claim")
