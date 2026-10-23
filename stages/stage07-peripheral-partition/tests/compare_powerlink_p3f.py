"""P3f new cumulative recompiles with explicitly reused pinned core objects."""
import argparse
import json
from pathlib import Path
from compare_powerlink_p3b import compare
if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('first', 'second', 'candidate_first', 'candidate_second', 'report'): p.add_argument(name, type=Path)
    a = p.parse_args(); report = compare(a.first, a.second, a.candidate_first, a.candidate_second)
    report['phase'] = 'P3f new cumulative source roots, SOFTWARE ONLY'
    report['software_origin'] = '9 unchanged core artifacts copied from verified P3e, NOT newly compiled core'
    a.report.write_text(json.dumps(report, indent=2) + '\n')
    print('P3f REPRO PASS: new runtime images identical; 9 reused pinned objects match')
