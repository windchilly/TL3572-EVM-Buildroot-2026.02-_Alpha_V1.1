#!/usr/bin/env python3
"""Independent software builds; ELF debug paths excluded, runtime included."""
import argparse
import hashlib
import json
from pathlib import Path


def compare(first, second, candidate_first, candidate_second):
    items = []
    checks = [(first, second, name) for name in (
        "p1/core/aarch64/libm7_powerlink_mn_core.a", "p1/core/aarch64/mn-core.o",
        "p1/edrv-aarch64/libm7_powerlink_eth2_edrv.a", "p1/mn-core-edrv.o",
        "rtos-aarch64/libm7_powerlink_rtos.a", "mn-core-edrv-rtos.o")]
    checks += [(candidate_first, candidate_second, "demos/rk3572_mica/build/" + name)
               for name in ("up-a.runtime.bin", "up-b.runtime.bin", "mn-with-real-bsp.stripped.o")]
    for left, right, name in checks:
        data = (left / name).read_bytes()
        if data != (right / name).read_bytes():
            raise ValueError(f"Independent build mismatch: {name}")
        items.append({"artifact": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "byte_identical": True})
    return {"phase": "P2 software only; no timer MMIO/IRQ or MN runtime execution",
            "independent_build_roots": [str(x) for x in (first, second, candidate_first, candidate_second)],
            "artifacts": items, "formal_firmware_replaced": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("first", "second", "candidate_first", "candidate_second", "report"):
        p.add_argument(name, type=Path)
    a = p.parse_args()
    a.report.write_text(json.dumps(compare(a.first, a.second, a.candidate_first, a.candidate_second), indent=2) + "\n", encoding="utf-8")
    print("P2 REPRO PASS: 9 libraries/merged objects/runtime images byte-identical")
