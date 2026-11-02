"""Compare 9 AArch64 artifacts from fresh native+AArch64 builds; no ELF claim."""
import argparse
import hashlib
import json
from pathlib import Path
from compare_powerlink_p3a import ARTIFACTS
if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('first','second','report'):p.add_argument(name,type=Path)
    a=p.parse_args();artifacts=[]
    for name in ARTIFACTS:
        content=(a.first/name).read_bytes()
        if content!=(a.second/name).read_bytes():raise ValueError('fresh software build mismatch: '+name)
        artifacts.append(dict(path=name,bytes=len(content),sha256=hashlib.sha256(content).hexdigest()))
    report=dict(phase='P3i SOFTWARE ONLY; no candidate/board',identical=True,
        independent_roots=[str(a.first),str(a.second)],artifacts=artifacts,
        origin='Two fresh complete builds from pinned archive; no copied prebuilt libraries',
        hardware_tested=False,runtime_images_built=False)
    a.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('P3i REPRO PASS: 9 freshly rebuilt software artifacts byte-identical; NO runtime images or board')
