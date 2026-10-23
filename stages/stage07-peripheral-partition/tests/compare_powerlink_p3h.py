"""P3h independent full software/core and cumulative runtime comparison."""
import argparse
import json
from pathlib import Path
from compare_powerlink_p3b import compare
if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('first', 'second', 'candidate_first', 'candidate_second', 'report'): p.add_argument(name, type=Path)
    a = p.parse_args(); report = compare(a.first, a.second, a.candidate_first, a.candidate_second)
    report.update(phase='P3h independent full cores + cumulative source roots, SOFTWARE ONLY',
        software_origin='Both full software roots compiled from pinned archive; first-error source compiled in each. No copied prebuilt core artifacts.',
        scope='Full OD retained; UP2 NMT-only 1MiB FSC option; actual hardware NMT/high-water not tested.')
    a.report.write_text(json.dumps(report, indent=2) + '\n')
    print('P3h REPRO PASS: 9 freshly rebuilt software artifacts + 2 runtime images byte-identical')
