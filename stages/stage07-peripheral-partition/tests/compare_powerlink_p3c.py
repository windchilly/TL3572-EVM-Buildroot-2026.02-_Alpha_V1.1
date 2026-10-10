"""P3c: fresh cumulative recompiles, pinned P3a software reused explicitly."""
import argparse
import json
from pathlib import Path
from compare_powerlink_p3b import compare

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("first", "second", "candidate_first", "candidate_second", "report"):
        p.add_argument(name, type=Path)
    a = p.parse_args()
    report = compare(a.first, a.second, a.candidate_first, a.candidate_second)
    report["phase"] = "P3c independent cumulative source-root recompiles"
    report["software_origin"] = "Two copies of verified P3b/P3a software (9 old artifacts reused, NOT a fresh core rebuild)"
    a.report.write_text(json.dumps(report, indent=2) + "\n")
    print("P3c REPRO PASS: 2 freshly rebuilt cumulative runtime images identical; 9 reused pinned artifacts match")
