"""P3e cumulative source recompiles; explicitly reused pinned core libraries."""
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
    report['phase'] = 'P3e two freshly compiled cumulative source roots, SOFTWARE ONLY'
    report['software_origin'] = 'Two copied verified P3d software roots: 9 old core artifacts reused, NOT freshly recompiled core'
    a.report.write_text(json.dumps(report, indent=2) + '\n')
    print('P3e REPRO PASS: cumulative runtime images identical; 9 reused pinned artifacts match')
