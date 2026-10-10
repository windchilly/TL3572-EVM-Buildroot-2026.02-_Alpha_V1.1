#!/usr/bin/env python3
"""Compare P3a libraries plus P3b complete cumulative runtime images."""
import argparse
import hashlib
import json
from pathlib import Path
from compare_powerlink_p3a import ARTIFACTS


def compare(first, second, candidate_first, candidate_second):
    checks = [(first, second, name) for name in ARTIFACTS]
    checks += [(candidate_first, candidate_second, "demos/rk3572_mica/build/" + name)
               for name in ("up-a.runtime.bin", "up-b.runtime.bin")]
    results = []
    for left, right, name in checks:
        content = (left / name).read_bytes()
        if content != (right / name).read_bytes():
            raise ValueError(f"Independent build mismatch: {name}")
        results.append({"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    return {"phase": "P3b SOFTWARE ONLY", "independent_roots": [str(x) for x in
        (first, second, candidate_first, candidate_second)], "identical": True,
        "artifacts": results, "elf_debug_paths_excluded": True, "hardware_tested": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("first", "second", "candidate_first", "candidate_second", "report"):
        p.add_argument(name, type=Path)
    a = p.parse_args()
    a.report.write_text(json.dumps(compare(a.first, a.second, a.candidate_first, a.candidate_second), indent=2) + "\n", encoding="utf-8")
    print("P3b REPRO PASS: 9 full-stack libraries/objects + 2 cumulative runtime images byte-identical")
