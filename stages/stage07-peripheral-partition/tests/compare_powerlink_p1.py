#!/usr/bin/env python3
"""Compare independent P1 builds; ELF debug paths need not be byte-identical."""
import argparse
import hashlib
import json
from pathlib import Path


def compare(first, second, candidate_first, candidate_second):
    artifacts = []
    checks = [
        (first, second, "core/aarch64/libm7_powerlink_mn_core.a"),
        (first, second, "core/aarch64/mn-core.o"),
        (first, second, "edrv-aarch64/libm7_powerlink_eth2_edrv.a"),
        (first, second, "mn-core-edrv.o"),
        (candidate_first, candidate_second, "demos/rk3572_mica/build/up-a.runtime.bin"),
        (candidate_first, candidate_second, "demos/rk3572_mica/build/up-b.runtime.bin"),
    ]
    for left_root, right_root, relative in checks:
        left = (left_root / relative).read_bytes()
        right = (right_root / relative).read_bytes()
        if left != right:
            raise ValueError(f"Independent build mismatch: {relative}")
        artifacts.append({"artifact": relative, "bytes": len(left),
                          "sha256": hashlib.sha256(left).hexdigest(), "byte_identical": True})
    return {"phase": "P1 software only; no hardware execution or MN runtime",
            "independent_build_roots": [str(first), str(second), str(candidate_first), str(candidate_second)],
            "artifacts": artifacts, "elf_debug_path_identity_not_required": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("first", "second", "candidate_first", "candidate_second", "report"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    result = compare(args.first, args.second, args.candidate_first, args.candidate_second)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("P1 REPRO PASS: core+EDRV libraries/merged objects and both cumulative runtime images identical")
