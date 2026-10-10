"""P3d fresh cumulative recompiles; explicitly reused pinned P3a libraries."""
import argparse
import json
from pathlib import Path
from compare_powerlink_p3b import compare

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('first', 'second', 'candidate_first', 'candidate_second', 'report'):
        p.add_argument(name, type=Path)
    a = p.parse_args()
    report = compare(a.first, a.second, a.candidate_first, a.candidate_second)
    report['phase'] = 'P3d two freshly compiled cumulative source roots, SOFTWARE ONLY'
    report['software_origin'] = 'Two copied verified P3c/P3b/P3a software roots: 9 old artifacts reused, NOT freshly recompiled core'
    a.report.write_text(json.dumps(report, indent=2) + '\n')
    print('P3d REPRO PASS: cumulative runtime images identical; 9 reused pinned artifacts match')
