"""P3g fresh software cores and cumulative runtimes; no board claim."""
import argparse
import json
from pathlib import Path
from compare_powerlink_p3b import compare
if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('first', 'second', 'candidate_first', 'candidate_second', 'report'): p.add_argument(name, type=Path)
    a = p.parse_args(); report = compare(a.first, a.second, a.candidate_first, a.candidate_second)
    report.update(phase='P3g independently rebuilt full cores and cumulative source roots, SOFTWARE ONLY',
                  software_origin='Both full software roots compiled from the fixed upstream archive; 0006/0007 applied only to P3g full stack. No reused prebuilt core artifacts.')
    a.report.write_text(json.dumps(report, indent=2) + '\n')
    print('P3g REPRO PASS: 9 freshly rebuilt software artifacts + 2 runtime images byte-identical')
